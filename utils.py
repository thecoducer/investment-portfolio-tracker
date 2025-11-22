"""
Utility functions for session management, market operations, and common patterns.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


class SessionManager:
    """Handles session token caching and validation."""
    
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def load(self):
        """Load cached session tokens from file."""
        if not os.path.exists(self.cache_file):
            return
        
        try:
            with open(self.cache_file, "r") as f:
                cache_data = json.load(f)
            
            for account_name, session_info in cache_data.items():
                expiry_str = session_info.get("expiry")
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue
                
                self.sessions[account_name] = {
                    "access_token": session_info.get("access_token"),
                    "expiry": expiry
                }
            
            print(f"Loaded cached sessions for: {', '.join(self.sessions.keys())}")
        except Exception as e:
            print(f"Error loading session cache: {e}")
    
    def save(self):
        """Save session tokens to file."""
        try:
            cache_data = {}
            for account_name, session_info in self.sessions.items():
                cache_data[account_name] = {
                    "access_token": session_info.get("access_token"),
                    "expiry": session_info["expiry"].isoformat()
                }
            
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            
            print(f"Saved session cache for: {', '.join(cache_data.keys())}")
        except Exception as e:
            print(f"Error saving session cache: {e}")
    
    def _is_token_expired(self, expiry: datetime) -> bool:
        """Check if a token has expired."""
        return datetime.now(timezone.utc) >= expiry
    
    def is_valid(self, account_name: str) -> bool:
        """Check if account session token is still valid."""
        sess = self.sessions.get(account_name)
        if not sess:
            return False
        return not self._is_token_expired(sess["expiry"])
    
    def set_token(self, account_name: str, access_token: str, hours: int = 23, minutes: int = 50):
        """Store a new access token with expiry."""
        self.sessions[account_name] = {
            "access_token": access_token,
            "expiry": datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)
        }
    
    def get_token(self, account_name: str) -> str:
        """Get access token for account."""
        return self.sessions.get(account_name, {}).get("access_token")
    
    def get_validity(self) -> Dict[str, bool]:
        """Get validity status for all accounts."""
        return {name: self.is_valid(name) for name in self.sessions.keys()}


class StateManager:
    """Manages application state with thread safety."""
    
    def __init__(self):
        self.refresh_state = "updating"  # Start with updating state
        self.ltp_fetch_state = "updated"
        self.last_error: str = None
        self.last_run_ts: float = None
        self.holdings_last_updated: float = None
    
    def _set_state(self, state_attr: str, value: str):
        """Helper to set any state attribute."""
        setattr(self, state_attr, value)
    
    def set_refresh_running(self, error: str = None):
        """Set refresh state to updating."""
        self._set_state('refresh_state', 'updating')
        if error:
            self.last_error = error
    
    def set_refresh_idle(self):
        """Mark refresh as complete and update timestamp."""
        self._set_state('refresh_state', 'updated')
        self.last_run_ts = __import__('time').time()
    
    def set_ltp_running(self):
        """Set LTP fetch to updating."""
        self._set_state('ltp_fetch_state', 'updating')
    
    def set_ltp_idle(self):
        """Mark LTP fetch as complete and update the holdings timestamp."""
        self._set_state('ltp_fetch_state', 'updated')
        self.holdings_last_updated = __import__('time').time()
    
    def set_holdings_updated(self):
        """Mark holdings as updated with current timestamp."""
        self.holdings_last_updated = __import__('time').time()
    
    def is_any_running(self) -> bool:
        """Check if any operation is currently updating."""
        return self.refresh_state == "updating" or self.ltp_fetch_state == "updating"
    
    def get_combined_state(self) -> str:
        """Get combined state for UI (either 'updating' or 'updated')."""
        return "updating" if self.is_any_running() else "updated"


def format_timestamp(ts: float) -> str:
    """Format Unix timestamp to readable format."""
    if ts is None:
        return None
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def is_market_open_ist() -> bool:
    """Check if equity market is currently open."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(tz)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def validate_accounts(accounts: List[Dict[str, str]]):
    """Validate that all required account fields are present."""
    missing = []
    for acc in accounts:
        api_key = acc.get("api_key", "")
        api_secret = acc.get("api_secret", "")
        
        if not api_key or not api_secret:
            missing.append(acc.get("name", "<unknown>"))
    
    if missing:
        raise RuntimeError(f"Missing API credentials for accounts: {', '.join(missing)}")
