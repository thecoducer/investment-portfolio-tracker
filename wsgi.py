#!/usr/bin/env python3
"""
WSGI entry point for production deployment (Gunicorn / Cloud Run).

Usage:
    gunicorn wsgi:app -c gunicorn.conf.py
"""

# ---------------------------------------------------------------------------
# gRPC + gevent compatibility
# ---------------------------------------------------------------------------
# Gunicorn's gevent worker monkey-patches stdlib sockets, but gRPC's C-core
# uses its own networking and will deadlock unless explicitly told to
# cooperate with gevent.  This MUST run before any gRPC channel is created
# (i.e. before Firestore client initialisation).
# ---------------------------------------------------------------------------
try:
    import grpc.experimental.gevent as _grpc_gevent
    _grpc_gevent.init_gevent()
except ImportError:
    pass

from dotenv import load_dotenv
load_dotenv()  # must run before any app imports that read os.environ

import signal
import sys
import threading

from app.logging_config import configure, logger
from app.routes import app_ui

# Configure logging before anything else
configure()

# Expose the Flask app for Gunicorn
app = app_ui


def _start_background_services():
    """Start background data fetching and auto-refresh (once per worker)."""
    from app.fetchers import fetch_nifty50_data, run_auto_refresh

    logger.info("Starting background services...")
    fetch_nifty50_data()
    threading.Thread(target=run_auto_refresh, daemon=True, name="AutoRefresh").start()


def _graceful_shutdown(signum, frame):
    """Handle SIGTERM from Cloud Run / container orchestrator."""
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — shutting down gracefully...", sig_name)
    # Gunicorn handles worker cleanup; we just log and exit.
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)

# Start background services on import (runs once per Gunicorn worker)
_start_background_services()
