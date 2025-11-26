"""
Constants used throughout the portfolio tracker application.
"""

# Status states
STATE_UPDATING = "updating"
STATE_UPDATED = "updated"
STATE_ERROR = "error"

# Market Hours (IST)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 0
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
WEEKEND_SATURDAY = 5

# Default configuration values
DEFAULT_REQUEST_TOKEN_TIMEOUT = 180  # seconds
DEFAULT_AUTO_REFRESH_INTERVAL = 60  # seconds
DEFAULT_CALLBACK_HOST = "127.0.0.1"
DEFAULT_CALLBACK_PORT = 5000
DEFAULT_CALLBACK_PATH = "/callback"
DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 8000

# File paths
SESSION_CACHE_FILENAME = ".session_cache.json"
CONFIG_FILENAME = "config.json"

# HTTP Status codes
HTTP_OK = 200
HTTP_ACCEPTED = 202
HTTP_CONFLICT = 409

# Time format
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
