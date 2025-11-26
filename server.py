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

from flask import Flask, request, jsonify, Response, render_template, make_response

from utils import SessionManager, StateManager, load_config, validate_accounts, format_timestamp, is_market_open_ist
from api import AuthenticationManager, HoldingsService, SIPService
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
    DEFAULT_AUTO_REFRESH_INTERVAL
)

# Load configuration
CONFIG = load_config(os.path.join(os.path.dirname(__file__), CONFIG_FILENAME))

# Extract config values
ACCOUNTS_CONFIG = CONFIG.get("accounts", [])
SERVER_CONFIG = CONFIG.get("server", {})
TIMEOUT_CONFIG = CONFIG.get("timeouts", {})
FEATURE_CONFIG = CONFIG.get("features", {})

CALLBACK_HOST = SERVER_CONFIG.get("callback_host", DEFAULT_CALLBACK_HOST)
CALLBACK_PORT = SERVER_CONFIG.get("callback_port", DEFAULT_CALLBACK_PORT)
CALLBACK_PATH = SERVER_CONFIG.get("callback_path", DEFAULT_CALLBACK_PATH)
REDIRECT_URL = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"

UI_HOST = SERVER_CONFIG.get("ui_host", DEFAULT_UI_HOST)
UI_PORT = SERVER_CONFIG.get("ui_port", DEFAULT_UI_PORT)

REQUEST_TOKEN_TIMEOUT = TIMEOUT_CONFIG.get("request_token_timeout_seconds", DEFAULT_REQUEST_TOKEN_TIMEOUT)
AUTO_REFRESH_INTERVAL = TIMEOUT_CONFIG.get("auto_refresh_interval_seconds", DEFAULT_AUTO_REFRESH_INTERVAL)

AUTO_REFRESH_OUTSIDE_MARKET_HOURS = FEATURE_CONFIG.get("auto_refresh_outside_market_hours", False)

# Nifty 50 configuration
NIFTY50_REFRESH_INTERVAL = FEATURE_CONFIG.get("nifty50_refresh_interval_seconds", 120)
NIFTY50_FALLBACK_SYMBOLS = [
    "ADANIPORTS", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BHARTIARTL", "BPCL", "BRITANNIA", "CIPLA",
    "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM",
    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "ITC",
    "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI",
    "NESTLEIND", "NTPC", "ONGC", "POWERGRID", "RELIANCE",
    "SBILIFE", "SBIN", "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM",
    "TATAMOTORS", "TATASTEEL", "TCS", "TECHM", "TITAN",
    "ULTRACEMCO", "WIPRO", "APOLLOHOSP", "ADANIENT", "LTIM"
]

SESSION_CACHE_FILE = os.path.join(os.path.dirname(__file__), SESSION_CACHE_FILENAME)

# Flask apps
app_callback = Flask("callback_server")
app_callback.template_folder = os.path.join(os.path.dirname(__file__), "templates")
app_ui = Flask("ui_server")
app_ui.template_folder = os.path.join(os.path.dirname(__file__), "templates")
app_ui.static_folder = os.path.join(os.path.dirname(__file__), "static")

# Enable JSON compression for faster responses
app_ui.config['JSON_SORT_KEYS'] = False
app_ui.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Global state
merged_holdings_global: List[Dict[str, Any]] = []
merged_mf_holdings_global: List[Dict[str, Any]] = []
merged_sips_global: List[Dict[str, Any]] = []
nifty50_data_global: List[Dict[str, Any]] = []
nifty50_last_updated: float = 0  # Timestamp of last Nifty 50 update

fetch_in_progress = threading.Event()
nifty50_fetch_in_progress = threading.Event()


# --------------------------
# HELPER FUNCTIONS
# --------------------------
def log_error(context: str, error: Exception, account_name: str = None) -> None:
    """Log error with consistent formatting.
    
    Args:
        context: Description of what failed
        error: The exception that occurred
        account_name: Optional account name for context
    """
    account_info = f" for {account_name}" if account_name else ""
    print(f"Error {context}{account_info}: {error}")

# SSE (Server-Sent Events) support
class SSEClientManager:
    """Manages SSE client connections and broadcasts."""
    def __init__(self):
        self.clients: List[Queue] = []
        self.lock = threading.Lock()
    
    def add_client(self, client_queue: Queue):
        with self.lock:
            self.clients.append(client_queue)
    
    def remove_client(self, client_queue: Queue):
        with self.lock:
            try:
                self.clients.remove(client_queue)
            except ValueError:
                pass
    
    def broadcast(self, message: str):
        with self.lock:
            for client_queue in self.clients[:]:
                try:
                    client_queue.put_nowait(message)
                except:
                    self.remove_client(client_queue)

sse_manager = SSEClientManager()

# Manager instances
session_manager = SessionManager(SESSION_CACHE_FILE)
state_manager = StateManager()
auth_manager = AuthenticationManager(session_manager, REQUEST_TOKEN_TIMEOUT)
holdings_service = HoldingsService()
sip_service = SIPService()


# --------------------------
# SSE HELPER FUNCTIONS
# --------------------------
def broadcast_state_change():
    """Broadcast state change to all connected SSE clients."""
    message = json.dumps(_build_status_response())
    sse_manager.broadcast(message)


def _build_status_response() -> Dict[str, Any]:
    """Build status response dict - used by both /status endpoint and SSE."""
    return {
        "state": state_manager.get_combined_state(),
        "ltp_fetch_state": state_manager.ltp_fetch_state,
        "last_error": state_manager.last_error,
        "last_run_at": format_timestamp(state_manager.last_run_ts),
        "holdings_last_updated": format_timestamp(state_manager.holdings_last_updated),
        "session_validity": session_manager.get_validity(),
        "market_open": is_market_open_ist(),
        "nifty50_last_updated": nifty50_last_updated
    }

# Register state change listener
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


def _json_response_with_cache(data, sort_key=None, max_age=30):
    """Helper to create JSON response with caching headers."""
    sorted_data = sorted(data, key=lambda x: x.get(sort_key, "")) if sort_key else data
    response = jsonify(sorted_data)
    response.headers['Cache-Control'] = f'private, max-age={max_age}'
    return response

@app_ui.route("/holdings_data", methods=["GET"])
def holdings_data():
    """Return stock holdings as JSON."""
    return _json_response_with_cache(merged_holdings_global, sort_key="tradingsymbol")

@app_ui.route("/mf_holdings_data", methods=["GET"])
def mf_holdings_data():
    """Return MF holdings as JSON."""
    return _json_response_with_cache(merged_mf_holdings_global, sort_key="tradingsymbol")

@app_ui.route("/sips_data", methods=["GET"])
def sips_data():
    """Return active SIPs as JSON."""
    return _json_response_with_cache(merged_sips_global, sort_key="tradingsymbol")

@app_ui.route("/nifty50_data", methods=["GET"])
def nifty50_data():
    """Return cached Nifty 50 stocks data."""
    return _json_response_with_cache(nifty50_data_global)


@app_ui.route("/refresh", methods=["POST"])
def refresh_route():
    """Trigger a refresh of holdings data."""
    if fetch_in_progress.is_set():
        return make_response(jsonify({"error": "Fetch already in progress"}), HTTP_CONFLICT)

    # Check if any account session is expired
    needs_login = any(not session_manager.is_valid(acc["name"]) for acc in ACCOUNTS_CONFIG)
    run_background_fetch(force_login=needs_login)
    
    # Also trigger Nifty 50 refresh immediately
    fetch_nifty50_data()
    
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
def fetch_account_holdings(account_config: Dict[str, Any], force_login: bool = False) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Authenticate and fetch holdings and SIPs for an account.
    
    Args:
        account_config: Account configuration dict with name and env variable keys
        force_login: Force new login even if cached token exists
    
    Returns:
        Tuple of (stock_holdings, mf_holdings, sips)
    """
    kite = auth_manager.authenticate(account_config, force_login)
    stock_holdings, mf_holdings = holdings_service.fetch_holdings(kite)
    sips = sip_service.fetch_sips(kite)
    return stock_holdings, mf_holdings, sips


def run_background_fetch(force_login: bool = False):
    """Fetch holdings and SIPs in background thread."""
    def _target():
        try:
            fetch_in_progress.set()
            state_manager.set_refresh_running()
            
            all_stock_holdings = []
            all_mf_holdings = []
            all_sips = []

            # Fetch accounts sequentially
            for account_config in ACCOUNTS_CONFIG:
                account_name = account_config["name"]
                try:
                    stock_holdings, mf_holdings, sips = fetch_account_holdings(
                        account_config, force_login
                    )
                    
                    holdings_service.add_account_info(stock_holdings, account_name)
                    holdings_service.add_account_info(mf_holdings, account_name)
                    sip_service.add_account_info(sips, account_name)
                    
                    all_stock_holdings.append(stock_holdings)
                    all_mf_holdings.append(mf_holdings)
                    all_sips.append(sips)
                except Exception as e:
                    log_error("fetching holdings", e, account_name)
                    state_manager.last_error = str(e)

            merged_stocks, merged_mfs = holdings_service.merge_holdings(all_stock_holdings, all_mf_holdings)
            merged_sips = sip_service.merge_items(all_sips)
            
            global merged_holdings_global, merged_mf_holdings_global, merged_sips_global
            merged_holdings_global = merged_stocks
            merged_mf_holdings_global = merged_mfs
            merged_sips_global = merged_sips
            state_manager.set_holdings_updated()
            state_manager.set_refresh_idle()
            
            # Also refresh Nifty 50 data
            fetch_nifty50_data()

        except Exception as e:
            state_manager.last_error = str(e)
            state_manager.set_refresh_idle()
        finally:
            fetch_in_progress.clear()

    threading.Thread(target=_target, daemon=True).start()


# --------------------------
# NIFTY 50 DATA FETCHING
# --------------------------
def fetch_nifty50_symbols():
    """Fetch Nifty 50 constituent symbols from NSE API."""
    import requests
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        # First establish session with NSE
        session = requests.Session()
        session.get('https://www.nseindia.com', headers=headers, timeout=10)
        
        # Fetch Nifty 50 constituents
        url = 'https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050'
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            symbols = []
            
            for item in data.get('data', []):
                symbol = item.get('symbol')
                if symbol and symbol != 'NIFTY 50':  # Exclude index itself
                    symbols.append(symbol)
            
            return symbols
        else:
            print(f"Failed to fetch Nifty 50 symbols: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error fetching Nifty 50 symbols: {e}")
        return []


def fetch_nifty50_data():
    """Fetch Nifty 50 stocks data from NSE API and update global state."""
    if nifty50_fetch_in_progress.is_set():
        print("Nifty 50 fetch already in progress, skipping")
        return
    
    def _target():
        import requests
        
        try:
            nifty50_fetch_in_progress.set()
            print("Fetching Nifty 50 data...")
            
            # Fetch constituent symbols dynamically
            symbols = fetch_nifty50_symbols()
            
            if not symbols:
                print("No Nifty 50 symbols fetched, using fallback list")
                symbols = NIFTY50_FALLBACK_SYMBOLS
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            session = requests.Session()
            session.get('https://www.nseindia.com', headers=headers, timeout=10)
            
            nifty50_data = []
            
            for symbol in symbols:
                try:
                    # URL encode the symbol to handle special characters like & in M&M
                    from urllib.parse import quote
                    encoded_symbol = quote(symbol)
                    url = f"https://www.nseindia.com/api/quote-equity?symbol={encoded_symbol}"
                    response = session.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        price_info = data.get('priceInfo', {})
                        
                        nifty50_data.append({
                            'symbol': symbol,
                            'name': data.get('info', {}).get('companyName', symbol),
                            'ltp': price_info.get('lastPrice', 0),
                            'change': price_info.get('change', 0),
                            'pChange': price_info.get('pChange', 0),
                            'open': price_info.get('open', 0),
                            'high': price_info.get('intraDayHighLow', {}).get('max', 0),
                            'low': price_info.get('intraDayHighLow', {}).get('min', 0),
                            'close': price_info.get('previousClose', 0)
                        })
                    else:
                        nifty50_data.append({
                            'symbol': symbol,
                            'name': symbol,
                            'ltp': 0,
                            'change': 0,
                            'pChange': 0,
                            'open': 0,
                            'high': 0,
                            'low': 0,
                            'close': 0
                        })
                    
                    time.sleep(0.2)
                    
                except Exception as e:
                    print(f"Error fetching {symbol}: {e}")
                    nifty50_data.append({
                        'symbol': symbol,
                        'name': symbol,
                        'ltp': 0,
                        'change': 0,
                        'pChange': 0,
                        'open': 0,
                        'high': 0,
                        'low': 0,
                        'close': 0
                    })
            
            global nifty50_data_global, nifty50_last_updated
            nifty50_data_global = nifty50_data
            nifty50_last_updated = time.time()
            print(f"Nifty 50 data updated: {len(nifty50_data)} stocks")
            
            broadcast_state_change()
            
        except Exception as e:
            print(f"Error in Nifty 50 fetch: {e}")
        finally:
            nifty50_fetch_in_progress.clear()
    
    threading.Thread(target=_target, daemon=True).start()


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
            print(f"Auto-refresh skipped: {skip_reason}")
            continue
        
        market_status = "outside market hours" if not market_open else "during market hours"
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"Auto-refresh triggered at {timestamp} ({market_status})")
        run_background_fetch(force_login=False)


# --------------------------
# NIFTY 50 AUTO-REFRESH
# --------------------------
def run_nifty50_auto_refresh():
    """
    Periodically refresh Nifty 50 data independently from portfolio refresh.
    Runs more frequently (default: every 2 minutes).
    """
    time.sleep(10)  # Wait for initial fetch to complete
    
    while True:
        time.sleep(NIFTY50_REFRESH_INTERVAL)
        
        market_open = is_market_open_ist()
        should_run, skip_reason = _should_auto_refresh(market_open, False)
        
        if not should_run:
            print(f"Nifty 50 auto-refresh skipped: {skip_reason}")
            continue
        
        market_status = "outside market hours" if not market_open else "during market hours"
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"Nifty 50 auto-refresh triggered at {timestamp} ({market_status})")
        fetch_nifty50_data()


# --------------------------
# SERVER MANAGEMENT
# --------------------------
def start_server(app: Flask, host: str, port: int) -> threading.Thread:
    """Start a Flask app in a daemon thread."""
    def _run():
        app.run(host=host, port=port, debug=False, use_reloader=False)
    
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.5)
    return t


def main():
    """Start the application."""
    try:
        # Load cached sessions
        session_manager.load()
        
        # Validate accounts
        validate_accounts(ACCOUNTS_CONFIG)
        
        print(f"Starting callback server at {REDIRECT_URL}")
        start_server(app_callback, CALLBACK_HOST, CALLBACK_PORT)
        
        dashboard_url = f"http://{UI_HOST}:{UI_PORT}/holdings"
        print(f"Starting UI server at {dashboard_url}")
        start_server(app_ui, UI_HOST, UI_PORT)
        
        print("Server is ready. Press CTRL+C to stop.")
        
        # Open browser automatically
        print(f"Opening dashboard in browser: {dashboard_url}")
        threading.Timer(1.5, lambda: webbrowser.open(dashboard_url)).start()
        
        # Trigger initial holdings refresh and set status to updating
        print("Triggering initial holdings refresh...")
        run_background_fetch(force_login=False)
        
        # Start background auto-refresh service
        print(f"Starting auto-refresh service (interval: {AUTO_REFRESH_INTERVAL}s)")
        threading.Thread(target=run_auto_refresh, daemon=True).start()
        
        # Start Nifty 50 auto-refresh service
        print(f"Starting Nifty 50 auto-refresh service (interval: {NIFTY50_REFRESH_INTERVAL}s)")
        threading.Thread(target=run_nifty50_auto_refresh, daemon=True).start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
