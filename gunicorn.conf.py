"""Gunicorn configuration for production deployment.

Optimised for SSE (long-lived connections) on Google Cloud Run.
Uses gevent async workers so each SSE connection does NOT block a thread.
"""

import multiprocessing
import os

# --- Server socket ---
bind = "0.0.0.0:" + os.environ.get("PORT", "8080")

# --- Worker processes ---
# Cloud Run: typically 1 worker (CPU is throttled per request).
# On VM / GKE: 2 * CPU + 1 is the classic formula.
workers = int(os.environ.get("WEB_CONCURRENCY", 1))

# gevent worker — non-blocking IO, ideal for SSE streaming responses.
worker_class = "gevent"

# Max concurrent connections per worker (each SSE connection = 1 greenlet).
worker_connections = int(os.environ.get("WORKER_CONNECTIONS", 500))

# --- Timeouts ---
# Keep-alive for upstream proxies (Cloud Run uses HTTP/1.1 keep-alive).
keepalive = 65

# Worker silence timeout — how long a worker can be silent before master
# considers it dead.  Must be > SSE keepalive interval (30 s).
timeout = 120

# Graceful shutdown window (seconds) — matches Cloud Run's default.
graceful_timeout = 30

# --- Logging ---
accesslog = "-"       # stdout
errorlog = "-"        # stderr
loglevel = os.environ.get("LOG_LEVEL", "info")

# Don't log health-check noise
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# --- Security ---
limit_request_line = 8190
limit_request_fields = 100

# --- Process naming ---
proc_name = "metron"

# --- Server hooks ---
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Metron starting with %d worker(s) [%s]", workers, worker_class)


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
