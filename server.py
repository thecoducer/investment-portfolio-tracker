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
from typing import List, Dict, Any
import json
import webbrowser
from datetime import datetime
from queue import Queue, Empty
from logging_config import logger, configure

from flask import Flask, request, jsonify, Response, render_template, make_response

from utils import SessionManager, StateManager, load_config, validate_accounts, format_timestamp, is_market_open_ist
from api import AuthenticationManager, HoldingsService, SIPService, NSEAPIClient, ZerodhaAPIClient
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
    NIFTY50_FALLBACK_SYMBOLS
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


# --------------------------
# STATUS AND BROADCASTING
# --------------------------

def _build_status_response() -> Dict[str, Any]:
    """Build comprehensive status response for API and SSE.
    
    Returns:
        Dict containing application state, timestamps, and session info
    """
    return {
        "last_error": state_manager.last_error,
        "portfolio_state": state_manager.portfolio_state,
        "portfolio_last_updated": format_timestamp(state_manager.portfolio_last_updated),
        "nifty50_state": state_manager.nifty50_state,
        "nifty50_last_updated": format_timestamp(state_manager.nifty50_last_updated),
        "market_open": is_market_open_ist(),
        "session_validity": session_manager.get_validity()
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

@app_ui.route("/refresh", methods=["POST"])
def refresh_route():
    """Trigger a refresh of holdings data."""
    if fetch_in_progress.is_set():
        return make_response(jsonify({"error": "Fetch already in progress"}), HTTP_CONFLICT)

    # Check if any account session is expired
    needs_login = any(not session_manager.is_valid(acc["name"]) for acc in ACCOUNTS_CONFIG)
    run_background_fetch(force_login=needs_login)
    
    return make_response(jsonify({"status": "started", "needs_login": needs_login}), HTTP_ACCEPTED)


@app_ui.route("/holdings", methods=["GET"])
def holdings_page():
    """Serve the main holdings page."""
    return render_template("holdings.html")


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
            session = nse_client._create_session()
            nifty50_data = [
                nse_client.fetch_stock_quote(session, symbol)
                for symbol in symbols
            ]
            
            # Update global cache
            global nifty50_data_global
            nifty50_data_global = nifty50_data
            
            logger.info("Nifty 50 data updated: %d stocks", len(nifty50_data_global))
        except Exception as e:
            logger.exception("Error fetching Nifty 50 data: %s", e)
            error_occurred = str(e)
        finally:
            state_manager.set_nifty50_updated(error=error_occurred)
            nifty50_fetch_in_progress.clear()
    
    threading.Thread(target=_fetch_task, daemon=True).start()


def run_background_fetch(force_login: bool = False, on_complete=None) -> None:
    """Orchestrate concurrent fetching of portfolio and market data.
    
    Launches two parallel background tasks:
    1. Portfolio data (holdings and SIPs) from Zerodha
    2. Nifty 50 market data from NSE
    
    Args:
        force_login: If True, force re-authentication for portfolio data
        on_complete: Optional callback to execute after both tasks complete
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
        
        # Start both threads
        portfolio_thread.start()
        nifty50_thread.start()
        
        # Wait for completion
        portfolio_thread.join()
        nifty50_thread.join()
        
        # Execute callback if provided
        if on_complete:
            on_complete()
    
    threading.Thread(target=_orchestrate_fetch, daemon=True).start()


# --------------------------
# AUTOMATIC REFRESH
# --------------------------
def _should_auto_refresh(market_open: bool, in_progress: bool) -> tuple[bool, str]:
    """Check if auto-refresh should run and return reason if not.
    
    Returns:
        (should_run, skip_reason)
    """
    if not market_open and not AUTO_REFRESH_OUTSIDE_MARKET_HOURS:
        return False, "market closed and auto_refresh_outside_market_hours disabled"
    
    if in_progress:
        return False, "manual refresh in progress"
    
    return True, None

def run_auto_refresh():
    """
    Periodically trigger full holdings refresh.
    
    Auto-refresh behavior:
    - During market hours: Always runs
    - Outside market hours: Only if AUTO_REFRESH_OUTSIDE_MARKET_HOURS is True
    """
    while True:
        time.sleep(AUTO_REFRESH_INTERVAL)
        
        market_open = is_market_open_ist()
        should_run, skip_reason = _should_auto_refresh(market_open, fetch_in_progress.is_set())
        
        if not should_run:
            logger.info("Auto-refresh skipped: %s", skip_reason)
            continue

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
        
        # Trigger initial data fetch, then start auto-refresh
        logger.info("Triggering initial data refresh...")
        run_background_fetch(force_login=False, on_complete=_start_auto_refresh_service)
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.exception("Fatal error occurred: %s", e)


if __name__ == "__main__":
    main()
