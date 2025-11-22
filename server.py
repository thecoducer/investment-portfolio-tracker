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

from flask import Flask, request, jsonify, Response, render_template, make_response
from pytz import timezone
from datetime import datetime

from utils import SessionManager, StateManager, load_config, validate_accounts, format_timestamp, is_market_open_ist
from api import AuthenticationManager, HoldingsService, LTPService, SIPService
from constants import (
    STATE_UPDATING,
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
    DEFAULT_LTP_FETCH_INTERVAL
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
LTP_FETCH_INTERVAL = TIMEOUT_CONFIG.get("ltp_fetch_interval_seconds", DEFAULT_LTP_FETCH_INTERVAL)

AUTO_LTP_UPDATE = FEATURE_CONFIG.get("auto_ltp_update", True)

SESSION_CACHE_FILE = os.path.join(os.path.dirname(__file__), SESSION_CACHE_FILENAME)

# Flask apps
app_callback = Flask("callback_server")
app_callback.template_folder = os.path.join(os.path.dirname(__file__), "templates")
app_ui = Flask("ui_server")
app_ui.template_folder = os.path.join(os.path.dirname(__file__), "templates")
app_ui.static_folder = os.path.join(os.path.dirname(__file__), "static")

# Global state
merged_holdings_global: List[Dict[str, Any]] = []
merged_mf_holdings_global: List[Dict[str, Any]] = []
merged_sips_global: List[Dict[str, Any]] = []

fetch_in_progress = threading.Event()

# Manager instances
session_manager = SessionManager(SESSION_CACHE_FILE)
state_manager = StateManager()
auth_manager = AuthenticationManager(session_manager, REQUEST_TOKEN_TIMEOUT)
holdings_service = HoldingsService()
ltp_service = LTPService()
sip_service = SIPService()


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
    return jsonify({
        "state": state,
        "ltp_fetch_state": ltp_state,
        "last_error": state_manager.last_error,
        "last_run_at": format_timestamp(state_manager.last_run_ts),
        "holdings_last_updated": format_timestamp(state_manager.holdings_last_updated),
        "session_validity": session_manager.get_validity()
    })


@app_ui.route("/holdings_data", methods=["GET"])
def holdings_data():
    """Return stock holdings as JSON."""
    sorted_holdings = sorted(merged_holdings_global, key=lambda h: h.get("tradingsymbol", ""))
    return jsonify(sorted_holdings)


@app_ui.route("/mf_holdings_data", methods=["GET"])
def mf_holdings_data():
    """Return MF holdings as JSON."""
    sorted_mf = sorted(merged_mf_holdings_global, key=lambda h: h.get("tradingsymbol", ""))
    return jsonify(sorted_mf)


@app_ui.route("/sips_data", methods=["GET"])
def sips_data():
    """Return active SIPs as JSON."""
    sorted_sips = sorted(merged_sips_global, key=lambda s: s.get("tradingsymbol", ""))
    return jsonify(sorted_sips)


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
# LTP FETCHING
# --------------------------
def run_ltp_fetcher():
    """
    Periodically fetch latest trading prices for stocks.
    
    Feature Flag (AUTO_LTP_UPDATE):
    - True: Run LTP fetcher regardless of market open status (for testing)
    - False: Only run LTP fetcher when market is open (production behavior)
    """
    if not AUTO_LTP_UPDATE:
        # If disabled, just keep thread alive but do nothing
        while True:
            time.sleep(10)
        return
    
    while True:
        time.sleep(1)
        
        # If no holdings loaded yet, wait before attempting fetch
        if not merged_holdings_global:
            time.sleep(LTP_FETCH_INTERVAL)
            continue
        
        # Feature flag logic:
        # - If AUTO_LTP_UPDATE is True: skip market check, always run
        # - If AUTO_LTP_UPDATE is False: check market open status
        if not AUTO_LTP_UPDATE and not is_market_open_ist():
            time.sleep(LTP_FETCH_INTERVAL)
            continue

        state_manager.set_ltp_running()
        try:
            ltp_data = ltp_service.fetch_ltps(merged_holdings_global)
            ltp_service.update_holdings_with_ltp(merged_holdings_global, ltp_data)
        except Exception as e:
            print(f"Error fetching LTPs: {e}")
        finally:
            state_manager.set_ltp_idle()
            time.sleep(LTP_FETCH_INTERVAL)


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
        
        # Start background services
        threading.Thread(target=run_ltp_fetcher, daemon=True).start()
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
