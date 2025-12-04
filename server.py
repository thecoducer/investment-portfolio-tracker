#!/usr/bin/env python3
"""
Investment Portfolio Tracker Server
Fetches holdings from Zerodha KiteConnect API and displays a dashboard.

Usage:
    1. Set up environment: pip install -r requirements.txt
    2. Configure accounts in config.json
    3. Set environment variables: export KITE_API_KEY_MAYUKH=... etc.
    4. Run: python server.py
"""

import os
import threading
import time
from typing import List, Dict, Any, Optional
import json
import webbrowser
from datetime import datetime
from queue import Queue, Empty
from requests.exceptions import Timeout, ConnectionError
from logging_config import logger, configure

from flask import Flask, request, jsonify, Response, render_template, make_response

from utils import SessionManager, StateManager, load_config, validate_accounts, format_timestamp, is_market_open_ist
from api import AuthenticationManager, HoldingsService, SIPService, NSEAPIClient, ZerodhaAPIClient
from api.google_sheets_client import GoogleSheetsClient, PhysicalGoldService, GOOGLE_SHEETS_AVAILABLE
from api.ibja_gold_price import get_gold_price_service
from api.physical_gold import enrich_holdings_with_prices
from error_handler import ErrorAggregator, ErrorHandler
from constants import (
    HTTP_ACCEPTED,
    HTTP_CONFLICT,
    SESSION_CACHE_FILENAME,
    CONFIG_FILENAME,
    DEFAULT_CALLBACK_HOST,
    DEFAULT_CALLBACK_PORT,
    DEFAULT_CALLBACK_PATH,
    DEFAULT_UI_HOST,
    DEFAULT_UI_PORT,
    DEFAULT_REQUEST_TOKEN_TIMEOUT,
    DEFAULT_AUTO_REFRESH_INTERVAL,
    NIFTY50_FALLBACK_SYMBOLS,
    GOLD_PRICE_FETCH_HOURS
)

# --------------------------
# CONFIGURATION
# --------------------------

def _load_application_config():
    """Load and parse application configuration from config.json.
    
    Returns:
        Tuple of configuration values for the application
    """
    config = load_config(os.path.join(os.path.dirname(__file__), CONFIG_FILENAME))
    
    accounts_config = config.get("accounts", [])
    server_config = config.get("server", {})
    timeout_config = config.get("timeouts", {})
    feature_config = config.get("features", {})
    
    callback_host = server_config.get("callback_host", DEFAULT_CALLBACK_HOST)
    callback_port = server_config.get("callback_port", DEFAULT_CALLBACK_PORT)
    callback_path = server_config.get("callback_path", DEFAULT_CALLBACK_PATH)
    
    ui_host = server_config.get("ui_host", DEFAULT_UI_HOST)
    ui_port = server_config.get("ui_port", DEFAULT_UI_PORT)
    
    request_token_timeout = timeout_config.get("request_token_timeout_seconds", DEFAULT_REQUEST_TOKEN_TIMEOUT)
    auto_refresh_interval = timeout_config.get("auto_refresh_interval_seconds", DEFAULT_AUTO_REFRESH_INTERVAL)
    
    auto_refresh_outside_market_hours = feature_config.get("auto_refresh_outside_market_hours", False)
    
    session_cache_file = os.path.join(os.path.dirname(__file__), SESSION_CACHE_FILENAME)
    redirect_url = f"http://{callback_host}:{callback_port}{callback_path}"
    
    return (
        accounts_config, callback_host, callback_port, callback_path, redirect_url,
        ui_host, ui_port, request_token_timeout, auto_refresh_interval,
        auto_refresh_outside_market_hours, session_cache_file
    )

# Load configuration
(
    ACCOUNTS_CONFIG, CALLBACK_HOST, CALLBACK_PORT, CALLBACK_PATH, REDIRECT_URL,
    UI_HOST, UI_PORT, REQUEST_TOKEN_TIMEOUT, AUTO_REFRESH_INTERVAL,
    AUTO_REFRESH_OUTSIDE_MARKET_HOURS, SESSION_CACHE_FILE
) = _load_application_config()

# --------------------------
# FLASK APPLICATIONS
# --------------------------

def _create_flask_app(name: str, enable_static: bool = False) -> Flask:
    """Create and configure a Flask application.
    
    Args:
        name: Application name
        enable_static: Whether to enable static folder
    
    Returns:
        Configured Flask app instance
    """
    app = Flask(name)
    base_dir = os.path.dirname(__file__)
    app.template_folder = os.path.join(base_dir, "templates")
    
    if enable_static:
        app.static_folder = os.path.join(base_dir, "static")
        # Optimize JSON responses
        app.config['JSON_SORT_KEYS'] = False
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    
    return app

app_callback = _create_flask_app("callback_server")
app_ui = _create_flask_app("ui_server", enable_static=True)

# --------------------------
# GLOBAL STATE
# --------------------------

# Portfolio data cache
merged_holdings_global: List[Dict[str, Any]] = []
merged_mf_holdings_global: List[Dict[str, Any]] = []
merged_sips_global: List[Dict[str, Any]] = []
nifty50_data_global: List[Dict[str, Any]] = []
physical_gold_holdings_global: List[Dict[str, Any]] = []
gold_prices_cache: Dict[str, Dict[str, float]] = {}  # Cache for IBJA gold prices
gold_prices_last_fetch: Optional[datetime] = None  # Timestamp of last gold price fetch

# Thread synchronization
fetch_in_progress = threading.Event()
nifty50_fetch_in_progress = threading.Event()

# --------------------------
# SERVER-SENT EVENTS (SSE)
# --------------------------

class SSEClientManager:
    """Manages Server-Sent Events client connections and message broadcasting."""
    
    def __init__(self):
        self.clients: List[Queue] = []
        self.lock = threading.Lock()
    
    def add_client(self, client_queue: Queue) -> None:
        """Add a new SSE client connection."""
        with self.lock:
            self.clients.append(client_queue)
    
    def remove_client(self, client_queue: Queue) -> None:
        """Remove an SSE client connection."""
        with self.lock:
            try:
                self.clients.remove(client_queue)
            except ValueError:
                pass
    
    def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected SSE clients."""
        with self.lock:
            for client_queue in self.clients[:]:
                try:
                    client_queue.put_nowait(message)
                except Exception:
                    logger.exception("Failed to send SSE message to client, removing")
                    self.remove_client(client_queue)


# --------------------------
# SERVICE INSTANCES
# --------------------------

# SSE management
sse_manager = SSEClientManager()

# Core services
session_manager = SessionManager(SESSION_CACHE_FILE)
state_manager = StateManager()
auth_manager = AuthenticationManager(session_manager, REQUEST_TOKEN_TIMEOUT)
holdings_service = HoldingsService()
sip_service = SIPService()
zerodha_client = ZerodhaAPIClient(auth_manager, holdings_service, sip_service)

# Physical Gold services (optional - requires Google Sheets API setup)
google_sheets_client = None
physical_gold_service = None

def _initialize_physical_gold_service():
    """Initialize Google Sheets client for physical gold tracking."""
    global google_sheets_client, physical_gold_service
    
    if not GOOGLE_SHEETS_AVAILABLE:
        logger.info("Physical Gold tracking unavailable: Google Sheets libraries not installed")
        return
    
    config = load_config(os.path.join(os.path.dirname(__file__), CONFIG_FILENAME))
    google_sheets_config = config.get("features", {}).get("fetch_physical_gold_from_google_sheets", {})
    
    if not google_sheets_config.get("enabled", False):
        logger.info("Physical Gold tracking disabled in configuration")
        return
    
    credentials_file = google_sheets_config.get("credentials_file")
    if credentials_file and os.path.exists(credentials_file):
        google_sheets_client = GoogleSheetsClient(credentials_file)
        physical_gold_service = PhysicalGoldService(google_sheets_client)
        logger.info("Physical Gold tracking initialized")
    else:
        logger.warning("Physical Gold tracking unavailable: credentials file not found")

_initialize_physical_gold_service()


# --------------------------
# STATUS AND BROADCASTING
# --------------------------

def _all_sessions_valid() -> bool:
    """Check if all account sessions are valid.
    
    Returns:
        True if all sessions are valid, False otherwise
    """
    return all(session_manager.is_valid(acc["name"]) for acc in ACCOUNTS_CONFIG)


def _build_status_response() -> Dict[str, Any]:
    """Build comprehensive status response for API and SSE.
    
    Returns:
        Dict containing application state, timestamps, and session info
    """
    # Get all account names from config
    all_account_names = [acc["name"] for acc in ACCOUNTS_CONFIG]
    
    return {
        "last_error": state_manager.last_error,
        "portfolio_state": state_manager.portfolio_state,
        "portfolio_last_updated": format_timestamp(state_manager.portfolio_last_updated),
        "nifty50_state": state_manager.nifty50_state,
        "nifty50_last_updated": format_timestamp(state_manager.nifty50_last_updated),
        "physical_gold_state": state_manager.physical_gold_state,
        "physical_gold_last_updated": format_timestamp(state_manager.physical_gold_last_updated),
        "market_open": is_market_open_ist(),
        "session_validity": session_manager.get_validity(all_account_names),
        "waiting_for_login": state_manager.waiting_for_login
    }


def broadcast_state_change() -> None:
    """Broadcast state change to all connected SSE clients."""
    message = json.dumps(_build_status_response())
    sse_manager.broadcast(message)


# Register state change listener for automatic broadcasting
state_manager.add_change_listener(broadcast_state_change)


# --------------------------
# CALLBACK SERVER
# --------------------------
@app_callback.route(CALLBACK_PATH, methods=["GET"])
def callback():
    """Handle OAuth callback from KiteConnect login."""
    req_token = request.args.get("request_token")
    if req_token:
        auth_manager.set_request_token(req_token)
        return render_template("callback_success.html")
    return render_template("callback_error.html")


# --------------------------
# UI SERVER ROUTES
# --------------------------
@app_ui.route("/status", methods=["GET"])
def status():
    """Return current application status and session validity."""
    response = jsonify(_build_status_response())
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/events", methods=["GET"])
def events():
    """Server-Sent Events endpoint for real-time status updates."""
    def event_stream():
        client_queue = Queue(maxsize=10)
        sse_manager.add_client(client_queue)
        
        try:
            # Send initial state
            yield f"data: {json.dumps(_build_status_response())}\n\n"
            
            # Stream updates
            while True:
                try:
                    message = client_queue.get(timeout=30)
                    yield f"data: {message}\n\n"
                except Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            sse_manager.remove_client(client_queue)
    
    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })

def _create_json_response_no_cache(data: List[Dict[str, Any]], sort_key: str = None) -> Response:
    """Create JSON response with no-cache headers and optional sorting.
    
    Args:
        data: Data to serialize as JSON
        sort_key: Optional key to sort data by
    
    Returns:
        Flask Response object with JSON data and no-cache headers
    """
    sorted_data = sorted(data, key=lambda x: x.get(sort_key, "")) if sort_key else data
    response = jsonify(sorted_data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/holdings_data", methods=["GET"])
def holdings_data():
    """Return stock holdings as JSON."""
    return _create_json_response_no_cache(merged_holdings_global, sort_key="tradingsymbol")


@app_ui.route("/mf_holdings_data", methods=["GET"])
def mf_holdings_data():
    """Return mutual fund holdings as JSON."""
    return _create_json_response_no_cache(merged_mf_holdings_global, sort_key="fund")


@app_ui.route("/sips_data", methods=["GET"])
def sips_data():
    """Return active SIPs (Systematic Investment Plans) as JSON."""
    return _create_json_response_no_cache(merged_sips_global, sort_key="status")


@app_ui.route("/nifty50_data", methods=["GET"])
def nifty50_data():
    """Return Nifty 50 stocks data as JSON."""
    return _create_json_response_no_cache(nifty50_data_global, sort_key="symbol")


@app_ui.route("/physical_gold_data", methods=["GET"])
def physical_gold_data():
    """Return physical gold holdings as JSON with latest IBJA prices."""
    # Use cached gold prices (updated during refresh)
    enriched_holdings = enrich_holdings_with_prices(physical_gold_holdings_global, gold_prices_cache)
    return _create_json_response_no_cache(enriched_holdings, sort_key="date")


@app_ui.route("/refresh", methods=["POST"])
def refresh_route():
    """Trigger a refresh of holdings data."""
    if fetch_in_progress.is_set():
        return make_response(jsonify({"error": "Fetch already in progress"}), HTTP_CONFLICT)

    # Check if any account session is expired
    needs_login = not _all_sessions_valid()
    run_background_fetch(force_login=needs_login, is_manual=True)
    
    return make_response(jsonify({"status": "started", "needs_login": needs_login}), HTTP_ACCEPTED)


@app_ui.route("/holdings", methods=["GET"])
def holdings_page():
    """Serve the main holdings page."""
    config = load_config(os.path.join(os.path.dirname(__file__), CONFIG_FILENAME))
    physical_gold_enabled = config.get("features", {}).get("fetch_physical_gold_from_google_sheets", {}).get("enabled", False)
    return render_template("holdings.html", physical_gold_enabled=physical_gold_enabled)


@app_ui.route("/nifty50", methods=["GET"])
def nifty50_page():
    """Serve the Nifty 50 stocks page."""
    return render_template("nifty50.html")


# --------------------------
# DATA FETCHING
# --------------------------
def fetch_portfolio_data(force_login: bool = False) -> None:
    """Fetch holdings and SIPs for all configured accounts.
    
    This function:
    - Fetches stock holdings, mutual fund holdings, and SIPs from all accounts
    - Updates the global state with merged results
    - Handles errors gracefully and updates state accordingly
    
    Args:
        force_login: If True, force re-authentication even if cached tokens exist
    """
    fetch_in_progress.set()
    state_manager.set_portfolio_updating()
    error_occurred = None
    
    try:
        # Fetch data from all accounts in parallel
        merged_stocks, merged_mfs, merged_sips, error_occurred = \
            zerodha_client.fetch_all_accounts_data(ACCOUNTS_CONFIG, force_login)
        
        # Update global state with fetched data
        global merged_holdings_global, merged_mf_holdings_global, merged_sips_global
        merged_holdings_global = merged_stocks
        merged_mf_holdings_global = merged_mfs
        merged_sips_global = merged_sips
        
        if not error_occurred:
            logger.info("Portfolio data updated: %d stocks, %d MFs, %d SIPs",
                       len(merged_stocks), len(merged_mfs), len(merged_sips))
    except Exception as e:
        logger.exception("Error fetching portfolio data: %s", e)
        error_occurred = str(e)
    finally:
        state_manager.set_portfolio_updated(error=error_occurred)
        fetch_in_progress.clear()


def _should_fetch_gold_prices() -> bool:
    """Check if gold prices should be fetched based on schedule.
    
    Returns:
        True if prices should be fetched (first load or scheduled times defined in GOLD_PRICE_FETCH_HOURS)
    """
    global gold_prices_last_fetch
    
    # First load - always fetch
    if gold_prices_last_fetch is None:
        return True
    
    now = datetime.now()
    today = now.date()
    last_fetch_date = gold_prices_last_fetch.date()
    
    # If last fetch was on a different day, allow fetching again
    if today != last_fetch_date:
        return True
    
    # Check if we're in one of the scheduled time windows
    current_hour = now.hour
    last_fetch_hour = gold_prices_last_fetch.hour
    
    # Allow fetch during scheduled hours if not already fetched in that hour
    if current_hour in GOLD_PRICE_FETCH_HOURS and last_fetch_hour != current_hour:
        return True
    
    return False


def fetch_physical_gold_data(force_gold_price_fetch: bool = False) -> None:
    """Fetch physical gold holdings from Google Sheets.
    
    This function:
    - Fetches physical gold data from configured Google Sheets
    - Updates the global physical gold holdings cache
    - Fetches and caches latest IBJA gold prices (on first load or scheduled times)
    - Runs silently if Google Sheets is not configured
    
    Args:
        force_gold_price_fetch: If True, bypass schedule and fetch gold prices immediately
    """
    global physical_gold_holdings_global, gold_prices_cache, gold_prices_last_fetch
    
    if not physical_gold_service:
        # Service not initialized - skip silently
        return
    
    state_manager.set_physical_gold_updating()
    error_occurred = False
    
    try:
        config = load_config(os.path.join(os.path.dirname(__file__), CONFIG_FILENAME))
        google_sheets_config = config.get("features", {}).get("fetch_physical_gold_from_google_sheets", {})
        
        spreadsheet_id = google_sheets_config.get("spreadsheet_id")
        range_name = google_sheets_config.get("range_name", "Sheet1!A:K")
        
        if not spreadsheet_id:
            state_manager.set_physical_gold_updated()
            return
        
        logger.info("Fetching Physical Gold data from Google Sheets...")
        holdings = physical_gold_service.fetch_holdings(spreadsheet_id, range_name)
        
        physical_gold_holdings_global = holdings
        logger.info("Physical Gold data updated: %d holdings", len(holdings))
        
        # Fetch and cache latest IBJA gold prices (on schedule or forced)
        should_fetch = force_gold_price_fetch or _should_fetch_gold_prices()
        
        if should_fetch:
            try:
                gold_service = get_gold_price_service()
                gold_prices = gold_service.fetch_gold_prices()
                if gold_prices:
                    gold_prices_cache = gold_prices
                    gold_prices_last_fetch = datetime.now()
                    logger.info("Gold prices updated: %s", list(gold_prices.keys()))
                else:
                    logger.warning("Failed to fetch gold prices - keeping cached prices if available")
            except Exception as gold_error:
                logger.error("Error fetching gold prices: %s - keeping cached prices", gold_error)
                # Don't fail physical gold fetch if gold prices fail - use cached prices
        else:
            scheduled_times = ", ".join([f"{h}:00" for h in GOLD_PRICE_FETCH_HOURS])
            logger.info(f"Skipping gold price fetch - using cached prices (next scheduled: {scheduled_times} IST)")
        
    except Exception as e:
        logger.exception("Error fetching Physical Gold data: %s", e)
        error_occurred = True
        # Don't fail the entire fetch if physical gold fails - preserve existing data
        if not physical_gold_holdings_global:
            physical_gold_holdings_global = []
        logger.info("Preserved %d existing physical gold holdings after fetch failure", 
                   len(physical_gold_holdings_global))
    finally:
        state_manager.set_physical_gold_updated(error="Failed to fetch physical gold data" if error_occurred else None)
        

def fetch_nifty50_data() -> None:
    """Fetch Nifty 50 index constituent stocks data from NSE API.
    
    This function:
    - Fetches the list of Nifty 50 constituent symbols
    - Retrieves real-time quotes for each stock
    - Updates the global Nifty 50 data cache
    - Runs asynchronously in a background thread
    """
    if nifty50_fetch_in_progress.is_set():
        logger.info("Nifty 50 fetch already in progress, skipping")
        return
    
    state_manager.set_nifty50_updating()

    def _fetch_task():
        """Background task to fetch Nifty 50 data."""
        error_occurred = None
        try:
            nifty50_fetch_in_progress.set()
            logger.info("Fetching Nifty 50 data...")
            
            # Initialize NSE API client
            nse_client = NSEAPIClient()
            
            # Fetch constituent symbols (with fallback)
            symbols = nse_client.fetch_nifty50_symbols()
            if not symbols:
                logger.warning("Failed to fetch symbols from NSE, using fallback list")
                symbols = NIFTY50_FALLBACK_SYMBOLS
            
            # Fetch quotes for all symbols
            try:
                session = nse_client._create_session()
            except (Timeout, ConnectionError) as e:
                logger.error("Failed to create NSE session: %s", e)
                raise  # Re-raise to be caught by outer exception handler
            
            nifty50_data = [
                nse_client.fetch_stock_quote(session, symbol)
                for symbol in symbols
            ]
            
            # Update global cache
            global nifty50_data_global
            nifty50_data_global = nifty50_data
            
            logger.info("Nifty 50 data updated: %d stocks", len(nifty50_data_global))
        except Timeout:
            logger.warning("NSE website timeout - Nifty 50 data not updated (server slow)")
            error_occurred = "NSE website timeout"
        except ConnectionError:
            logger.warning("Cannot connect to NSE website - Nifty 50 data not updated")
            error_occurred = "Connection error"
        except Exception as e:
            logger.error("Error fetching Nifty 50 data: %s", str(e))
            error_occurred = str(e)
        finally:
            state_manager.set_nifty50_updated(error=error_occurred)
            nifty50_fetch_in_progress.clear()
    
    threading.Thread(target=_fetch_task, daemon=True).start()


def run_background_fetch(force_login: bool = False, on_complete=None, is_manual: bool = False) -> None:
    """Orchestrate concurrent fetching of portfolio and market data.
    
    Launches parallel background tasks:
    1. Portfolio data (holdings and SIPs) from Zerodha
    2. Nifty 50 market data from NSE
    3. Physical Gold data from Google Sheets (if configured)
    
    Args:
        force_login: If True, force re-authentication for portfolio data
        on_complete: Optional callback to execute after all tasks complete
        is_manual: If True, this is a manual refresh (always fetch gold prices)
    """
    def _orchestrate_fetch():
        """Coordinate parallel fetch operations."""
        portfolio_thread = threading.Thread(
            target=fetch_portfolio_data,
            args=(force_login,),
            daemon=True
        )
        nifty50_thread = threading.Thread(
            target=fetch_nifty50_data,
            daemon=True
        )
        # Force gold price fetch on manual refresh or first load
        force_gold_fetch = is_manual or (gold_prices_last_fetch is None)
        physical_gold_thread = threading.Thread(
            target=fetch_physical_gold_data,
            args=(force_gold_fetch,),
            daemon=True
        )
        
        # Start all threads
        portfolio_thread.start()
        nifty50_thread.start()
        physical_gold_thread.start()
        
        # Wait for completion
        portfolio_thread.join()
        nifty50_thread.join()
        physical_gold_thread.join()
        
        # Execute callback if provided
        if on_complete:
            on_complete()
    
    threading.Thread(target=_orchestrate_fetch, daemon=True).start()


# --------------------------
# AUTOMATIC REFRESH
# --------------------------
def _should_auto_refresh() -> tuple[bool, str]:
    """Check if auto-refresh should run and return reason if not.
    
    Returns:
        (should_run, skip_reason)
    """
    market_open = is_market_open_ist()
    
    if not market_open and not AUTO_REFRESH_OUTSIDE_MARKET_HOURS:
        return False, "market closed and auto_refresh_outside_market_hours disabled"
    
    if fetch_in_progress.is_set():
        return False, "manual refresh in progress"
    
    # Check if all sessions are valid
    if not _all_sessions_valid():
        return False, "one or more sessions invalid - manual login required"
    
    return True, None

def run_auto_refresh():
    """
    Periodically trigger full holdings refresh.
    
    Auto-refresh behavior:
    - During market hours: Runs only if all sessions are valid
    - Outside market hours: Only if AUTO_REFRESH_OUTSIDE_MARKET_HOURS is True and sessions are valid
    - Skips if any session is invalid (requires manual login via button)
    """
    while True:
        time.sleep(AUTO_REFRESH_INTERVAL)
        
        should_run, skip_reason = _should_auto_refresh()
        
        if not should_run:
            logger.info("Auto-refresh skipped: %s", skip_reason)
            continue

        market_open = is_market_open_ist()
        market_status = "outside market hours" if not market_open else "during market hours"
        timestamp = datetime.now().strftime('%H:%M:%S')
        logger.info("Auto-refresh triggered at %s (%s)", timestamp, market_status)
        run_background_fetch(force_login=False)


# --------------------------
# SERVER MANAGEMENT
# --------------------------
def start_server(app: Flask, host: str, port: int) -> threading.Thread:
    """Start a Flask application in a background daemon thread.
    
    Args:
        app: Flask application instance
        host: Host address to bind to
        port: Port number to bind to
    
    Returns:
        Thread object running the Flask server
    """
    def _run_server():
        app.run(host=host, port=port, debug=False, use_reloader=False)
    
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()
    time.sleep(0.5)  # Allow server to start
    return thread


def _start_auto_refresh_service() -> None:
    """Initialize and start the auto-refresh background service."""
    threading.Thread(target=run_auto_refresh, daemon=True).start()


def main():
    """Initialize and start the Investment Portfolio Tracker application.
    
    This function:
    1. Configures logging
    2. Loads cached authentication sessions
    3. Validates account configuration
    4. Starts callback and UI Flask servers
    5. Opens the dashboard in a web browser
    6. Triggers initial data fetch
    7. Starts the auto-refresh service
    8. Keeps the application running
    """
    try:
        # Initialize application
        configure()
        logger.info("Starting Investment Portfolio Tracker...")
        
        # Load cached sessions and validate configuration
        session_manager.load()
        validate_accounts(ACCOUNTS_CONFIG)
        
        # Start Flask servers
        logger.info("Starting callback server at %s", REDIRECT_URL)
        start_server(app_callback, CALLBACK_HOST, CALLBACK_PORT)
        
        dashboard_url = f"http://{UI_HOST}:{UI_PORT}/holdings"
        logger.info("Starting UI server at %s", dashboard_url)
        start_server(app_ui, UI_HOST, UI_PORT)
        
        logger.info("Servers ready. Press CTRL+C to stop.")
        
        # Open dashboard in browser
        logger.info("Opening dashboard in browser...")
        threading.Timer(1.5, lambda: webbrowser.open(dashboard_url)).start()
        
        # Always fetch only Nifty50 data on startup (portfolio requires user action)
        logger.info("Fetching initial Nifty50 data...")
        fetch_nifty50_data()
        
        # Start auto-refresh service (will check session validity before each refresh)
        _start_auto_refresh_service()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.exception("Fatal error occurred: %s", e)


if __name__ == "__main__":
    main()
