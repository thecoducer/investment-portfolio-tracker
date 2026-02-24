"""
Flask application creation and route definitions.

Contains both the OAuth callback server and the main UI server.
"""

import json
import os
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from flask import (Flask, Response, jsonify, make_response, render_template,
                   request)

from .api.physical_gold import enrich_holdings_with_prices
from .cache import cache, fetch_in_progress
from .config import app_config
from .constants import HTTP_ACCEPTED, HTTP_CONFLICT, MARKET_INDEX_CACHE_TTL, SSE_KEEPALIVE_INTERVAL
from .services import (_all_sessions_valid, _build_status_response,
                       auth_manager, sse_manager)

# --------------------------
# FLASK APP FACTORIES
# --------------------------

def _create_flask_app(name: str, enable_static: bool = False) -> Flask:
    """Create and configure a Flask application.

    Args:
        name: Application name.
        enable_static: Whether to enable static folder.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(name)
    base_dir = os.path.dirname(__file__)
    app.template_folder = os.path.join(base_dir, "templates")

    if enable_static:
        app.static_folder = os.path.join(base_dir, "static")
        app.config['JSON_SORT_KEYS'] = False
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    return app


app_callback = _create_flask_app("callback_server")
app_ui = _create_flask_app("ui_server", enable_static=True)


# --------------------------
# HELPERS
# --------------------------

def _create_json_response_no_cache(data: List[Dict[str, Any]], sort_key: Optional[str] = None) -> Response:
    """Create JSON response with no-cache headers and optional sorting.

    Args:
        data: Data to serialize as JSON.
        sort_key: Optional key to sort data by.

    Returns:
        Flask Response with JSON data and no-cache headers.
    """
    sorted_data = sorted(data, key=lambda x: x.get(sort_key, "")) if sort_key else data
    response = jsonify(sorted_data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# --------------------------
# CALLBACK SERVER ROUTES
# --------------------------

@app_callback.route(app_config.callback_path, methods=["GET"])
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
            yield f"data: {json.dumps(_build_status_response())}\n\n"
            while True:
                try:
                    message = client_queue.get(timeout=SSE_KEEPALIVE_INTERVAL)
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
        'Connection': 'keep-alive',
    })


@app_ui.route("/stocks_data", methods=["GET"])
def stocks_data():
    """Return stock holdings as JSON."""
    return _create_json_response_no_cache(cache.stocks, sort_key="tradingsymbol")


@app_ui.route("/mf_holdings_data", methods=["GET"])
def mf_holdings_data():
    """Return mutual fund holdings as JSON."""
    return _create_json_response_no_cache(cache.mf_holdings, sort_key="fund")


@app_ui.route("/sips_data", methods=["GET"])
def sips_data():
    """Return SIPs (Systematic Investment Plans) as JSON."""
    return _create_json_response_no_cache(cache.sips, sort_key="status")


@app_ui.route("/nifty50_data", methods=["GET"])
def nifty50_data():
    """Return Nifty 50 stocks data as JSON."""
    return _create_json_response_no_cache(cache.nifty50, sort_key="symbol")


@app_ui.route("/physical_gold_data", methods=["GET"])
def physical_gold_data():
    """Return physical gold holdings as JSON with latest IBJA prices."""
    enriched_holdings = enrich_holdings_with_prices(cache.physical_gold, cache.gold_prices)
    return _create_json_response_no_cache(enriched_holdings, sort_key="date")


@app_ui.route("/fixed_deposits_data", methods=["GET"])
def fixed_deposits_data():
    """Return fixed deposits as JSON with maturity status."""
    return _create_json_response_no_cache(cache.fixed_deposits, sort_key="deposited_on")


@app_ui.route("/fd_summary_data", methods=["GET"])
def fd_summary_data():
    """Return pre-computed FD summary grouped by bank and account."""
    return _create_json_response_no_cache(cache.fd_summary)


@app_ui.route("/market_indices", methods=["GET"])
def market_indices():
    """Return NIFTY 50 and SENSEX market index data with TTL caching."""
    from datetime import datetime, timedelta
    from .api.nse_client import NSEAPIClient

    # Return cached data if still fresh
    if (cache.market_indices and cache.market_indices_last_fetch and
            datetime.now() - cache.market_indices_last_fetch < timedelta(seconds=MARKET_INDEX_CACHE_TTL)):
        response = jsonify(cache.market_indices)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    nse = NSEAPIClient()
    data = nse.fetch_market_indices()
    cache.market_indices = data
    cache.market_indices_last_fetch = datetime.now()

    response = jsonify(data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/refresh", methods=["POST"])
def refresh_route():
    """Trigger a refresh of stocks data."""
    # Deferred import to avoid circular dependency (fetchers -> services -> ... -> routes)
    from .fetchers import run_background_fetch

    if fetch_in_progress.is_set():
        return make_response(jsonify({"error": "Fetch already in progress"}), HTTP_CONFLICT)

    needs_login = not _all_sessions_valid()
    run_background_fetch(force_login=needs_login, is_manual=True)

    return make_response(jsonify({"status": "started", "needs_login": needs_login}), HTTP_ACCEPTED)


@app_ui.route("/", methods=["GET"])
def portfolio_page():
    """Serve the main portfolio page with feature flags."""
    features = app_config.features

    physical_gold_enabled = features.get(
        "fetch_physical_gold_from_google_sheets", {}
    ).get("enabled", False)

    fixed_deposits_enabled = features.get(
        "fetch_fixed_deposits_from_google_sheets", {}
    ).get("enabled", False)

    return render_template(
        "portfolio.html",
        physical_gold_enabled=physical_gold_enabled,
        fixed_deposits_enabled=fixed_deposits_enabled,
    )


@app_ui.route("/nifty50", methods=["GET"])
def nifty50_page():
    """Serve the Nifty 50 stocks page."""
    return render_template("nifty50.html")
