"""
Service instance initialization, status helpers, and state broadcasting.

This module wires together the core services used throughout the application
and provides shared helper functions for status reporting.
"""

import json
import os
from typing import Any, Dict

from .api import (AuthenticationManager, HoldingsService, SIPService,
                  ZerodhaAPIClient)
from .api.google_sheets_client import (GOOGLE_SHEETS_AVAILABLE,
                                       FixedDepositsService,
                                       GoogleSheetsClient, PhysicalGoldService)
from .config import app_config
from .logging_config import logger
from .sse import sse_manager
from .utils import (SessionManager, StateManager, format_timestamp,
                    is_market_open_ist)

# --------------------------
# CORE SERVICES
# --------------------------

session_manager = SessionManager(app_config.session_cache_file)
state_manager = StateManager()
auth_manager = AuthenticationManager(session_manager, app_config.request_token_timeout)
holdings_service = HoldingsService()
sip_service = SIPService()
zerodha_client = ZerodhaAPIClient(auth_manager, holdings_service, sip_service)

# --------------------------
# OPTIONAL GOOGLE SHEETS SERVICES
# --------------------------

google_sheets_client = None
physical_gold_service = None
fixed_deposits_service = None


def _initialize_google_sheets_services() -> None:
    """Initialize Google Sheets client and dependent services.

    Initializes Physical Gold and Fixed Deposits services if enabled in config.
    Reuses a single GoogleSheetsClient instance for efficiency.
    """
    global google_sheets_client, physical_gold_service, fixed_deposits_service

    if not GOOGLE_SHEETS_AVAILABLE:
        logger.info("Google Sheets services unavailable: libraries not installed")
        return

    features = app_config.features

    service_configs = [
        ("fetch_physical_gold_from_google_sheets", "Physical Gold", PhysicalGoldService, "physical_gold_service"),
        ("fetch_fixed_deposits_from_google_sheets", "Fixed Deposits", FixedDepositsService, "fixed_deposits_service"),
    ]

    for feature_key, service_name, service_class, var_name in service_configs:
        feature_config = features.get(feature_key, {})

        if not feature_config.get("enabled", False):
            logger.info("%s tracking disabled in configuration", service_name)
            continue

        credentials_file = feature_config.get("credentials_file")
        if credentials_file and not os.path.isabs(credentials_file):
            from .constants import CONFIG_DIR_NAME
            credentials_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), CONFIG_DIR_NAME, credentials_file
            )
        if not credentials_file or not os.path.exists(credentials_file):
            logger.warning("%s tracking unavailable: credentials file not found", service_name)
            continue

        if not google_sheets_client:
            google_sheets_client = GoogleSheetsClient(credentials_file)

        globals()[var_name] = service_class(google_sheets_client)
        logger.info("%s tracking initialized", service_name)


_initialize_google_sheets_services()


# --------------------------
# STATUS HELPERS
# --------------------------

def _all_sessions_valid() -> bool:
    """Check if all account sessions are valid."""
    return all(session_manager.is_valid(acc["name"]) for acc in app_config.accounts)


def _build_status_response() -> Dict[str, Any]:
    """Build comprehensive status response for API and SSE.

    Returns:
        Dictionary containing application state, timestamps, and session info.
    """
    all_account_names = [acc["name"] for acc in app_config.accounts]

    response = {
        "last_error": state_manager.last_error,
        "market_open": is_market_open_ist(),
        "session_validity": session_manager.get_validity(all_account_names),
        "waiting_for_login": state_manager.waiting_for_login,
    }
    for st in StateManager.STATE_TYPES:
        response[f"{st}_state"] = getattr(state_manager, f"{st}_state")
        response[f"{st}_last_updated"] = format_timestamp(
            getattr(state_manager, f"{st}_last_updated")
        )
    return response


def broadcast_state_change() -> None:
    """Broadcast current state to all connected SSE clients."""
    message = json.dumps(_build_status_response())
    sse_manager.broadcast(message)


# Register state change listener for automatic broadcasting
state_manager.add_change_listener(broadcast_state_change)
