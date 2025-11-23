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

fetch_in_progress = threading.Event()

# SSE (Server-Sent Events) support
sse_clients: List[Queue] = []
sse_lock = threading.Lock()

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
    with sse_lock:
        state = state_manager.get_combined_state()
        ltp_state = state_manager.ltp_fetch_state
        
        message = json.dumps({
            "state": state,
            "ltp_fetch_state": ltp_state,
            "last_error": state_manager.last_error,
            "last_run_at": format_timestamp(state_manager.last_run_ts),
            "holdings_last_updated": format_timestamp(state_manager.holdings_last_updated),
            "session_validity": session_manager.get_validity()
        })
        
        # Send to all connected clients
        for client_queue in sse_clients[:]:  # Use slice to avoid modification during iteration
            try:
                client_queue.put_nowait(message)
            except:
                # Remove disconnected clients
                try:
                    sse_clients.remove(client_queue)
                except ValueError:
                    pass


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
    state = state_manager.get_combined_state()
    ltp_state = state_manager.ltp_fetch_state
    
    # Return raw internal states for the UI to interpret
    response = jsonify({
        "state": state,
        "ltp_fetch_state": ltp_state,
        "last_error": state_manager.last_error,
        "last_run_at": format_timestamp(state_manager.last_run_ts),
        "holdings_last_updated": format_timestamp(state_manager.holdings_last_updated),
        "session_validity": session_manager.get_validity()
    })
    # Don't cache status as it changes frequently
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/events", methods=["GET"])
def events():
    """Server-Sent Events endpoint for real-time status updates."""
    def event_stream():
        # Create a queue for this client
        client_queue = Queue(maxsize=10)
        
        with sse_lock:
            sse_clients.append(client_queue)
        
        try:
            # Send initial state immediately
            state = state_manager.get_combined_state()
            ltp_state = state_manager.ltp_fetch_state
            
            initial_data = json.dumps({
                "state": state,
                "ltp_fetch_state": ltp_state,
                "last_error": state_manager.last_error,
                "last_run_at": format_timestamp(state_manager.last_run_ts),
                "holdings_last_updated": format_timestamp(state_manager.holdings_last_updated),
                "session_validity": session_manager.get_validity()
            })
            yield f"data: {initial_data}\n\n"
            
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for state changes with timeout for keepalive
                    message = client_queue.get(timeout=30)
                    yield f"data: {message}\n\n"
                except Empty:
                    # Send keepalive comment every 30 seconds
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected
            pass
        finally:
            # Clean up
            with sse_lock:
                try:
                    sse_clients.remove(client_queue)
                except ValueError:
                    pass
    
    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@app_ui.route("/holdings_data", methods=["GET"])
def holdings_data():
    """Return stock holdings as JSON."""
    sorted_holdings = sorted(merged_holdings_global, key=lambda h: h.get("tradingsymbol", ""))
    response = jsonify(sorted_holdings)
    # Add cache control for faster reloads
    response.headers['Cache-Control'] = 'private, max-age=30'
    return response


@app_ui.route("/mf_holdings_data", methods=["GET"])
def mf_holdings_data():
    """Return MF holdings as JSON."""
    sorted_mf = sorted(merged_mf_holdings_global, key=lambda h: h.get("tradingsymbol", ""))
    response = jsonify(sorted_mf)
    response.headers['Cache-Control'] = 'private, max-age=30'
    return response


@app_ui.route("/sips_data", methods=["GET"])
def sips_data():
    """Return active SIPs as JSON."""
    sorted_sips = sorted(merged_sips_global, key=lambda s: s.get("tradingsymbol", ""))
    response = jsonify(sorted_sips)
    response.headers['Cache-Control'] = 'private, max-age=30'
    return response


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
                try:
                    stock_holdings, mf_holdings, sips = fetch_account_holdings(account_config, force_login)
                    account_name = account_config["name"]
                    
                    holdings_service.add_account_info(stock_holdings, account_name)
                    holdings_service.add_account_info(mf_holdings, account_name)
                    sip_service.add_account_info(sips, account_name)
                    
                    all_stock_holdings.append(stock_holdings)
                    all_mf_holdings.append(mf_holdings)
                    all_sips.append(sips)
                except Exception as e:
                    print(f"Error fetching for {account_config['name']}: {e}")
                    state_manager.last_error = str(e)

            merged_stocks, merged_mfs = holdings_service.merge_holdings(all_stock_holdings, all_mf_holdings)
            merged_sips = sip_service.merge_items(all_sips)
            
            global merged_holdings_global, merged_mf_holdings_global, merged_sips_global
            merged_holdings_global = merged_stocks
            merged_mf_holdings_global = merged_mfs
            merged_sips_global = merged_sips
            state_manager.set_holdings_updated()
            state_manager.set_refresh_idle()

        except Exception as e:
            state_manager.last_error = str(e)
            state_manager.set_refresh_idle()
        finally:
            fetch_in_progress.clear()

    threading.Thread(target=_target, daemon=True).start()


# --------------------------
# AUTOMATIC REFRESH
# --------------------------
def run_auto_refresh():
    """
    Periodically trigger full holdings refresh (same as refresh button).
    
    Auto-refresh behavior:
    - During market hours (9 AM - 4:30 PM IST, weekdays): Always runs
    - Outside market hours: Only runs if AUTO_REFRESH_OUTSIDE_MARKET_HOURS is True
    
    Feature Flag (AUTO_REFRESH_OUTSIDE_MARKET_HOURS):
    - True: Run auto refresh 24/7 at specified intervals
    - False: Run auto refresh only during market hours (default)
    """
    while True:
        # Wait for the configured interval
        time.sleep(AUTO_REFRESH_INTERVAL)
        
        # Check if we should run auto-refresh based on market hours
        market_open = is_market_open_ist()
        
        # Skip if outside market hours and flag is disabled
        if not market_open and not AUTO_REFRESH_OUTSIDE_MARKET_HOURS:
            print(f"Auto-refresh skipped: market closed and auto_refresh_outside_market_hours disabled")
            continue
        
        # Skip if a manual refresh is already in progress
        if fetch_in_progress.is_set():
            print("Auto-refresh skipped: manual refresh in progress")
            continue
        
        # Trigger full refresh (same as refresh button)
        status_msg = "outside market hours" if not market_open else "during market hours"
        print(f"Auto-refresh triggered at {datetime.now().strftime('%H:%M:%S')} ({status_msg})")
        run_background_fetch(force_login=False)


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
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
