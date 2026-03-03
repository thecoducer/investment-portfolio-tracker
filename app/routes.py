"""Flask route definitions. All user data is scoped via session."""

import json
import os
import secrets
import threading
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from flask import (Flask, Response, jsonify, make_response, redirect,
                   render_template, request, session)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix

from .api.physical_gold import enrich_holdings_with_prices
from .cache import market_cache, portfolio_cache, user_sheets_cache
from .constants import (HTTP_ACCEPTED, HTTP_CONFLICT, MARKET_INDEX_CACHE_TTL,
                         SSE_KEEPALIVE_INTERVAL, SSE_TOKEN_MAX_AGE)
from .logging_config import logger
from .middleware import app_only, login_required, protected_api
from .services import (_build_status_response, ensure_user_loaded,
                       get_authenticated_accounts, get_user_accounts,
                       session_manager, sse_manager)
from .sse import EVICT_SENTINEL, SSE_MAX_CONNECTION_AGE, SSE_QUEUE_SIZE, SSE_RETRY_MS

# ---------------------------------------------------------------------------
# Cloud Run direct URL for SSE (bypasses Firebase Hosting CDN buffering)
# ---------------------------------------------------------------------------
CLOUD_RUN_URL = os.environ.get("CLOUD_RUN_URL", "").rstrip("/")

# ---------------------------------------------------------------------------
# SSE token signing (allows direct Cloud Run SSE without cookies)
# ---------------------------------------------------------------------------
_SSE_TOKEN_SALT = "sse-auth-token"


def _create_flask_app(name: str, enable_static: bool = False) -> Flask:
    app = Flask(name)
    base_dir = os.path.dirname(__file__)
    app.template_folder = os.path.join(base_dir, "templates")
    if enable_static:
        app.static_folder = os.path.join(base_dir, "static")
        app.config['JSON_SORT_KEYS'] = False
        app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    return app


app_ui = _create_flask_app("ui_server", enable_static=True)

# Trust proxy headers from Cloud Run / load balancers so request.url_root
# correctly reports https:// instead of http://.
app_ui.wsgi_app = ProxyFix(app_ui.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Session secret — MUST be a stable value in production so sessions survive
# container restarts.  A random fallback is used for local dev only.
_secret = os.environ.get("FLASK_SECRET_KEY")
if not _secret:
    logger.warning(
        "FLASK_SECRET_KEY not set — using a random key. "
        "Sessions will NOT survive restarts. Set this env var in production."
    )
    _secret = secrets.token_hex(32)
app_ui.secret_key = _secret

# Production session cookie settings
# IMPORTANT: Firebase Hosting strips ALL cookies except ``__session`` from both
# incoming requests and outgoing responses.  Flask's default cookie name is
# "session" which gets silently dropped, breaking OAuth and any session state.
app_ui.config.update(
    SESSION_COOKIE_NAME="__session",       # Firebase Hosting requirement
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") != "development",
)


# ---------------------------------------------------------------------------
# SSE token helpers (for direct Cloud Run SSE, bypassing Firebase CDN)
# ---------------------------------------------------------------------------

def _generate_sse_token(google_id: str) -> str:
    """Create a short-lived signed token for SSE authentication."""
    s = URLSafeTimedSerializer(app_ui.secret_key)
    return s.dumps({"gid": google_id}, salt=_SSE_TOKEN_SALT)


def _validate_sse_token(token: str) -> Optional[str]:
    """Validate an SSE token. Returns google_id or None."""
    s = URLSafeTimedSerializer(app_ui.secret_key)
    try:
        data = s.loads(token, salt=_SSE_TOKEN_SALT, max_age=SSE_TOKEN_MAX_AGE)
        return data.get("gid")
    except (BadSignature, SignatureExpired):
        return None


# ---------------------------------------------------------------------------
# Firebase Hosting detection
# ---------------------------------------------------------------------------
_FIREBASE_HOSTING_DOMAINS = frozenset({"metron.web.app", "metron.firebaseapp.com"})


def _is_firebase_hosting_request() -> bool:
    """Return True when the request was served through Firebase Hosting.

    When Firebase Hosting rewrites to Cloud Run the ``Host`` header is
    that of the Firebase domain (metron.web.app).  When the user browses
    Cloud Run directly, the Host is the ``*.run.app`` URL — in that case
    SSE can use the relative ``/events`` path with session cookies.
    """
    host = request.host.split(":")[0].lower()  # strip port
    return host in _FIREBASE_HOSTING_DOMAINS


def _add_cors_headers(response: Response) -> Response:
    """Add CORS headers for direct Cloud Run SSE access from Firebase Hosting."""
    origin = request.headers.get("Origin", "")
    allowed = False

    if origin:
        # Always allow Firebase Hosting origins
        try:
            from urllib.parse import urlparse
            host = urlparse(origin).hostname or ""
        except Exception:
            host = ""

        if host in _FIREBASE_HOSTING_DOMAINS:
            allowed = True
        # Allow any *.run.app origin (Cloud Run URL formats vary)
        elif host.endswith(".run.app"):
            allowed = True
        # Dev origins
        elif os.environ.get("FLASK_ENV") == "development" and host in ("localhost", "127.0.0.1"):
            allowed = True

    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    return response


# ---------------------------------------------------------------------------
# Health check (Cloud Run liveness / readiness probe)
# ---------------------------------------------------------------------------

@app_ui.route("/healthz", methods=["GET"])
def healthz():
    """Lightweight health check for Cloud Run / load balancer probes."""
    return jsonify({"status": "ok"}), 200


@app_ui.before_request
def _sync_spreadsheet_id():
    """Sync spreadsheet_id from Firebase if missing in session."""
    user = session.get("user")
    if user and not user.get("spreadsheet_id"):
        from .firebase_store import get_user
        existing = get_user(user["google_id"])
        if existing and existing.get("spreadsheet_id"):
            user["spreadsheet_id"] = existing["spreadsheet_id"]
            session["user"] = user
            session.modified = True


def _json_response(data: List[Dict[str, Any]], sort_key: Optional[str] = None) -> Response:
    """JSON response with no-cache headers and optional sorting."""
    sorted_data = sorted(data, key=lambda x: x.get(sort_key, "")) if sort_key else data
    resp = jsonify(sorted_data)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


def _current_user() -> Optional[Dict[str, Any]]:
    return session.get("user")


_user_fetch_locks: Dict[str, threading.Lock] = {}
_user_fetch_locks_guard = threading.Lock()
_USER_FETCH_LOCKS_MAX = 500  # prevent unbounded growth


def _get_user_fetch_lock(google_id: str) -> threading.Lock:
    with _user_fetch_locks_guard:
        # Evict oldest entries if the dict grows too large
        if len(_user_fetch_locks) >= _USER_FETCH_LOCKS_MAX:
            # Remove the first (oldest) half of entries
            keys_to_remove = list(_user_fetch_locks.keys())[: _USER_FETCH_LOCKS_MAX // 2]
            for k in keys_to_remove:
                _user_fetch_locks.pop(k, None)
        return _user_fetch_locks.setdefault(google_id, threading.Lock())


def _fetch_user_sheets_data(user):
    """Return (physical_gold, fixed_deposits) with TTL caching and per-user locking."""
    google_id = user.get("google_id", "")
    spreadsheet_id = user.get("spreadsheet_id")
    creds_dict = user.get("google_credentials")
    if not spreadsheet_id or not creds_dict:
        return None, None

    cached = user_sheets_cache.get(google_id)
    if cached:
        return cached.physical_gold, cached.fixed_deposits

    with _get_user_fetch_lock(google_id):
        cached = user_sheets_cache.get(google_id)
        if cached:
            return cached.physical_gold, cached.fixed_deposits

        try:
            from .api.google_auth import credentials_from_dict
            from .api.google_sheets_client import GoogleSheetsClient, PhysicalGoldService, FixedDepositsService
            from .api.fixed_deposits import calculate_current_value

            creds = credentials_from_dict(creds_dict)
            client = GoogleSheetsClient(user_credentials=creds)
            gold = PhysicalGoldService(client).fetch_holdings(spreadsheet_id, "Gold!A:F")
            deposits = calculate_current_value(
                FixedDepositsService(client).fetch_deposits(spreadsheet_id, "FixedDeposits!A:K"))

            user_sheets_cache.put(google_id, physical_gold=gold, fixed_deposits=deposits)
            return gold, deposits
        except Exception:
            logger.exception("Error fetching Sheets data")
            return None, None

@app_ui.route("/auth/google/login", methods=["GET"])
def google_login():
    """Redirect to Google OAuth consent screen."""
    from .api.google_auth import build_oauth_flow

    try:
        redirect_uri = request.url_root.rstrip("/") + "/auth/google/callback"
        logger.info("OAuth redirect_uri: %s", redirect_uri)
        flow = build_oauth_flow(redirect_uri)
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        session["oauth_state"] = state
        return redirect(authorization_url)
    except FileNotFoundError as e:
        logger.error("Google OAuth setup incomplete: %s", e)
        return render_template("auth_error.html",
                               error_title="Google Sign-In Not Configured",
                               error_message=str(e)), 500
    except Exception as e:
        logger.exception("Failed to start Google OAuth flow: %s", e)
        return render_template("auth_error.html",
                               error_title="Sign-In Error",
                               error_message=str(e)), 500


@app_ui.route("/auth/google/callback", methods=["GET"])
def google_callback():
    """Handle the OAuth 2.0 callback from Google."""
    from .api.google_auth import (
        credentials_to_dict,
        exchange_code_for_credentials,
        get_user_info,
    )
    from .api.user_sheets import create_portfolio_sheet
    from .firebase_store import get_user, update_spreadsheet_id, upsert_user

    code = request.args.get("code")
    if not code:
        return render_template("callback_error.html"), 400

    redirect_uri = request.url_root.rstrip("/") + "/auth/google/callback"

    try:
        credentials = exchange_code_for_credentials(code, redirect_uri)
        user_info = get_user_info(credentials)
        creds_dict = credentials_to_dict(credentials)

        google_id = user_info["id"]
        email = user_info.get("email", "")
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")

        existing = get_user(google_id)
        spreadsheet_id = existing.get("spreadsheet_id", "") if existing else ""

        user_doc = upsert_user(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
            google_credentials=creds_dict,
            spreadsheet_id=spreadsheet_id,
        )

        if not spreadsheet_id:
            def _create_sheet_bg(creds, title, gid):
                try:
                    sid = create_portfolio_sheet(creds, title=title)
                    update_spreadsheet_id(gid, sid)
                    logger.info("Background sheet creation done for %s", gid)
                except Exception:
                    logger.exception("Background sheet creation failed for %s", gid)
            threading.Thread(
                target=_create_sheet_bg,
                args=(credentials, f"Metron – {name or email}", google_id),
                daemon=True,
            ).start()

        session["user"] = {
            "google_id": google_id,
            "email": email,
            "name": name,
            "picture": picture,
            "spreadsheet_id": spreadsheet_id,
            "google_credentials": creds_dict,
        }

        return redirect("/")

    except Exception as e:
        logger.exception("Google OAuth callback failed: %s", e)
        return render_template("callback_error.html"), 500


@app_ui.route("/auth/me", methods=["GET"])
def auth_me():
    """Return current user info (or 401 if not signed in)."""
    user = _current_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "spreadsheet_id": user.get("spreadsheet_id"),
    })


@app_ui.route("/auth/logout", methods=["POST"])
@app_only
def auth_logout():
    """Sign out the current user."""
    session.clear()
    return jsonify({"status": "logged_out"})


@app_ui.route("/api/sse-token", methods=["GET"])
@protected_api
def sse_token():
    """Issue a short-lived signed token for direct Cloud Run SSE access.

    The token lets the browser open an EventSource directly to Cloud Run
    (bypassing Firebase Hosting CDN, which buffers streaming responses).
    """
    user = _current_user()
    token = _generate_sse_token(user["google_id"])
    resp = jsonify({"token": token, "ttl": SSE_TOKEN_MAX_AGE})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app_ui.route("/callback", methods=["GET"])
def zerodha_callback():
    """Handle Zerodha KiteConnect OAuth callback."""
    req_token = request.args.get("request_token")
    if not req_token:
        return render_template("callback_error.html")

    user = session.get("user")
    if not user or not user.get("google_id"):
        logger.warning("No active Google user in session during Zerodha callback")
        return render_template("callback_error.html")

    google_id = user["google_id"]
    ensure_user_loaded(google_id)

    accounts = get_user_accounts(google_id)
    authenticated_account = None
    for acc in accounts:
        if session_manager.is_valid(google_id, acc["name"]):
            continue
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=acc["api_key"])
            session_data = kite.generate_session(req_token, api_secret=acc["api_secret"])
            access_token = session_data.get("access_token")
            if access_token:
                session_manager.set_token(google_id, acc["name"], access_token)
                session_manager.save(google_id)
                authenticated_account = acc["name"]
                break
        except Exception:
            continue

    if not authenticated_account:
        return render_template("callback_error.html")

    logger.info("Login succeeded for %s/%s", google_id, authenticated_account)

    auth_accounts = [acc for acc in accounts if session_manager.is_valid(google_id, acc["name"])]
    if auth_accounts and not portfolio_cache.is_fetch_in_progress(google_id):
        from .fetchers import run_background_fetch
        run_background_fetch(google_id=google_id, accounts=auth_accounts)

    return render_template("callback_success.html")



@app_ui.route("/status", methods=["GET"])
@protected_api
def status():
    user = _current_user()
    google_id = user.get("google_id")
    response = jsonify(_build_status_response(google_id))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/events", methods=["GET", "OPTIONS"])
def events():
    """SSE endpoint for real-time per-user status updates.

    Authentication:
    - Via ``__session`` cookie (requests through Firebase Hosting), OR
    - Via ``?token=`` query param (direct Cloud Run access — Firebase CDN
      buffers streaming responses so the browser connects directly).

    Production hardening:
    - Connection age limit prevents zombie connections on GCloud.
    - ``retry:`` field tells browsers the reconnect interval.
    - Handles BrokenPipeError / ConnectionResetError gracefully.
    - Returns 503 when client limits are exceeded.
    - Queue size is bounded to prevent memory bloat.
    """
    # CORS preflight for direct Cloud Run access from Firebase domain
    if request.method == "OPTIONS":
        resp = Response("", status=204)
        return _add_cors_headers(resp)

    import time as _time

    # --- Authenticate: session cookie OR signed token ---
    google_id = None
    user = _current_user()
    if user:
        google_id = user.get("google_id")
    else:
        token = request.args.get("token")
        if token:
            google_id = _validate_sse_token(token)

    if not google_id:
        resp = jsonify({"error": "Authentication required"})
        resp.status_code = 401
        return _add_cors_headers(resp)

    def event_stream():
        client_queue = Queue(maxsize=SSE_QUEUE_SIZE)
        accepted = sse_manager.add_client(client_queue, google_id)
        if not accepted:
            # Limit exceeded — yield an error event and stop.
            yield f"retry: {SSE_RETRY_MS}\ndata: {{\"error\": \"too_many_connections\"}}\n\n"
            return

        started = _time.monotonic()
        try:
            # Send retry hint so browsers reconnect at a controlled interval
            yield f"retry: {SSE_RETRY_MS}\n"
            # Send initial state immediately
            yield f"data: {json.dumps(_build_status_response(google_id))}\n\n"
            while True:
                # Enforce max connection age (GCloud / load balancer timeouts)
                elapsed = _time.monotonic() - started
                if elapsed >= SSE_MAX_CONNECTION_AGE:
                    logger.info(
                        "SSE connection aged out for user=%s after %ds",
                        google_id, int(elapsed),
                    )
                    # Send a reconnect hint before closing
                    yield f"data: {{\"reconnect\": true}}\n\n"
                    break

                try:
                    message = client_queue.get(timeout=SSE_KEEPALIVE_INTERVAL)
                    if message is EVICT_SENTINEL:
                        logger.info(
                            "SSE connection evicted for user=%s (newer connection arrived)",
                            google_id,
                        )
                        # Tell client to reconnect immediately
                        yield f"data: {{\"reconnect\": true}}\n\n"
                        break
                    yield f"data: {message}\n\n"
                except Empty:
                    # SSE keepalive comment to prevent proxy/LB idle timeouts
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected normally
            pass
        except (BrokenPipeError, ConnectionResetError, OSError):
            # Client disconnected abnormally (common in production)
            logger.debug("SSE client disconnected (broken pipe) user=%s", google_id)
        except Exception:
            logger.exception("Unexpected error in SSE stream for user=%s", google_id)
        finally:
            sse_manager.remove_client(client_queue, google_id)

    resp = Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',              # HTTP/1.0 compat
        'X-Accel-Buffering': 'no',         # nginx / reverse proxies
        'X-Content-Type-Options': 'nosniff',
        'Connection': 'keep-alive',
        'Referrer-Policy': 'no-referrer',  # prevent token leaking via Referer header
    })
    return _add_cors_headers(resp)


@app_ui.route("/stocks_data", methods=["GET"])
@protected_api
def stocks_data():
    user = _current_user()
    user_data = portfolio_cache.get(user["google_id"])
    return _json_response(user_data.stocks, sort_key="tradingsymbol")


@app_ui.route("/mf_holdings_data", methods=["GET"])
@protected_api
def mf_holdings_data():
    user = _current_user()
    user_data = portfolio_cache.get(user["google_id"])
    return _json_response(user_data.mf_holdings, sort_key="fund")


@app_ui.route("/sips_data", methods=["GET"])
@protected_api
def sips_data():
    user = _current_user()
    user_data = portfolio_cache.get(user["google_id"])
    return _json_response(user_data.sips, sort_key="status")


@app_ui.route("/nifty50_data", methods=["GET"])
@app_only
def nifty50_data():
    return _json_response(market_cache.nifty50, sort_key="symbol")


@app_ui.route("/physical_gold_data", methods=["GET"])
@protected_api
def physical_gold_data():
    user = _current_user()
    gold, _ = _fetch_user_sheets_data(user)
    if gold is not None:
        enriched = enrich_holdings_with_prices(gold, market_cache.gold_prices)
        return _json_response(enriched, sort_key="date")
    return _json_response([], sort_key="date")


@app_ui.route("/fixed_deposits_data", methods=["GET"])
@protected_api
def fixed_deposits_data():
    user = _current_user()
    _, deposits = _fetch_user_sheets_data(user)
    if deposits is not None:
        return _json_response(deposits, sort_key="deposited_on")
    return _json_response([], sort_key="deposited_on")


@app_ui.route("/fd_summary_data", methods=["GET"])
@protected_api
def fd_summary_data():
    return _json_response([])


@app_ui.route("/market_indices", methods=["GET"])
@app_only
def market_indices():
    from datetime import datetime, timedelta
    from .api.market_data import MarketDataClient

    if (market_cache.market_indices and market_cache.market_indices_last_fetch and
            datetime.now() - market_cache.market_indices_last_fetch < timedelta(seconds=MARKET_INDEX_CACHE_TTL)):
        response = jsonify(market_cache.market_indices)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    client = MarketDataClient()
    data = client.fetch_market_indices()
    market_cache.market_indices = data
    market_cache.market_indices_last_fetch = datetime.now()

    response = jsonify(data)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app_ui.route("/refresh", methods=["POST"])
@protected_api
def refresh_route():
    """Trigger manual data refresh for the signed-in user."""
    from .fetchers import run_background_fetch

    user = _current_user()
    google_id = user["google_id"]

    if portfolio_cache.is_fetch_in_progress(google_id):
        return make_response(jsonify({"error": "Fetch already in progress"}), HTTP_CONFLICT)

    ensure_user_loaded(google_id)
    user_sheets_cache.invalidate(google_id)

    authenticated = get_authenticated_accounts(google_id)
    run_background_fetch(is_manual=True, accounts=authenticated, google_id=google_id)

    return make_response(jsonify({"status": "started"}), HTTP_ACCEPTED)


@app_ui.route("/", methods=["GET"])
def portfolio_page():
    """Serve landing page or portfolio dashboard with inlined data."""
    user = _current_user()
    if not user:
        return render_template("landing.html")

    google_id = user.get("google_id", "")
    ensure_user_loaded(google_id)

    user_data = portfolio_cache.get(google_id)
    initial_data = {
        "stocks": sorted(user_data.stocks, key=lambda x: x.get("tradingsymbol", "")),
        "mfHoldings": sorted(user_data.mf_holdings, key=lambda x: x.get("fund", "")),
        "sips": sorted(user_data.sips, key=lambda x: x.get("status", "")),
        "physicalGold": [],
        "fixedDeposits": [],
        "fdSummary": [],
        "status": _build_status_response(google_id),
    }

    # Only inject SSE direct config when the page is served through Firebase
    # Hosting (where the CDN buffers streaming responses).  When browsing
    # Cloud Run directly, relative /events works fine with session cookies.
    sse_base_url = CLOUD_RUN_URL if _is_firebase_hosting_request() else ""

    return render_template(
        "portfolio.html",
        physical_gold_enabled=True,
        fixed_deposits_enabled=True,
        user=user,
        initial_data_json=json.dumps(initial_data, default=str),
        sse_base_url=sse_base_url,
    )


@app_ui.route("/nifty50", methods=["GET"])
def nifty50_page():
    """Serve the Nifty 50 stocks page."""
    return render_template("nifty50.html")


@app_ui.route("/api/settings", methods=["GET"])
@protected_api
def get_settings():
    user = _current_user()
    from .firebase_store import get_zerodha_accounts
    google_id = user["google_id"]
    accounts = get_zerodha_accounts(google_id)
    names = [acc["name"] for acc in accounts]
    validity = session_manager.get_validity(google_id, names)

    login_urls = {}
    for acc in accounts:
        if not session_manager.is_valid(google_id, acc["name"]):
            try:
                from kiteconnect import KiteConnect
                login_urls[acc["name"]] = KiteConnect(api_key=acc["api_key"]).login_url()
            except Exception:
                pass

    return jsonify({"zerodha_accounts": names, "session_validity": validity, "login_urls": login_urls})


@app_ui.route("/api/settings/zerodha", methods=["POST"])
@protected_api
def add_zerodha():
    """Add a new Zerodha account for the signed-in user."""
    user = _current_user()
    data = request.get_json(silent=True) or {}
    account_name = (data.get("account_name") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    api_secret = (data.get("api_secret") or "").strip()

    if not account_name or not api_key or not api_secret:
        return jsonify({"error": "account_name, api_key, and api_secret are required"}), 400

    from .firebase_store import add_zerodha_account
    try:
        add_zerodha_account(user["google_id"], account_name, api_key, api_secret)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    return jsonify({"status": "saved", "account_name": account_name})


@app_ui.route("/api/settings/zerodha/<account_name>", methods=["DELETE"])
@protected_api
def remove_zerodha(account_name):
    """Remove a Zerodha account by name."""
    user = _current_user()
    from .firebase_store import remove_zerodha_account
    try:
        remove_zerodha_account(user["google_id"], account_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"status": "removed"})
