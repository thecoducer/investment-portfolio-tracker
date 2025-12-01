"""
Utility functions for session management, market operations, and common patterns.
"""
import json
import os
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from cryptography.fernet import Fernet
import platform
from zoneinfo import ZoneInfo
from logging_config import logger

from constants import (
    STATE_UPDATING,
    STATE_UPDATED,
    STATE_ERROR,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    WEEKEND_SATURDAY
)


class SessionManager:
    """Handles session token caching and validation with encryption."""
    
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._cipher = self._get_cipher()
    
    def _get_cipher(self) -> Fernet:
        """Generate a cipher using machine-specific data for encryption key."""
        machine_id = platform.node() + platform.machine()
        key_material = hashlib.sha256(machine_id.encode()).digest()
        from base64 import urlsafe_b64encode
        key = urlsafe_b64encode(key_material)
        return Fernet(key)
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt an access token."""
        return self._cipher.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt an access token."""
        try:
            return self._cipher.decrypt(encrypted_token.encode()).decode()
        except Exception:
            return encrypted_token
    
    def load(self):
        """Load cached session tokens from file and decrypt them."""
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
                
                # Decrypt the access token
                encrypted_token = session_info.get("access_token")
                access_token = self._decrypt_token(encrypted_token)
                
                self.sessions[account_name] = {
                    "access_token": access_token,
                    "expiry": expiry
                }
            
            logger.info("Loaded cached sessions for: %s", ', '.join(self.sessions.keys()))
        except Exception as e:
            logger.exception("Error loading session cache: %s", e)
    
    def save(self):
        """Save session tokens to file with encryption."""
        try:
            cache_data = {}
            for account_name, session_info in self.sessions.items():
                encrypted_token = self._encrypt_token(session_info.get("access_token"))
                
                cache_data[account_name] = {
                    "access_token": encrypted_token,
                    "expiry": session_info["expiry"].isoformat()
                }
            
            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)
            logger.info("Saved encrypted session cache for: %s", ', '.join(cache_data.keys()))
        except Exception as e:
            logger.exception("Error saving session cache: %s", e)
    
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
        self.portfolio_state = STATE_UPDATING  # Start with updating state
        self.nifty50_state = STATE_UPDATING  # Separate state for Nifty50 updates
        self.last_error: str = None
        self.portfolio_last_updated: float = None
        self.nifty50_last_updated: float = None
        self._change_listeners = []
    
    def _set_state(self, state_attr: str, value: str):
        """Helper to set any state attribute and notify listeners."""
        setattr(self, state_attr, value)
        self._notify_change()
    
    def _notify_change(self):
        """Notify all listeners that state has changed."""
        for listener in self._change_listeners:
            try:
                listener()
            except Exception as e:
                logger.exception("Error notifying listener: %s", e)
    
    def add_change_listener(self, callback):
        """Add a callback to be notified on state changes."""
        self._change_listeners.append(callback)
    
    def set_portfolio_updating(self, error: str = None):
        """Set portfolio state to updating and optionally set error."""
        self._set_state('portfolio_state', STATE_UPDATING)
        if error:
            self.last_error = error
    
    def set_portfolio_updated(self, error: str = None):
        """Mark portfolio refresh as complete and update timestamp.
        
        Args:
            error: Optional error message. If provided, state is set to ERROR.
        """
        if error:
            self.last_error = error
            self._set_state('portfolio_state', STATE_ERROR)
        else:
            self._set_state('portfolio_state', STATE_UPDATED)
            self.portfolio_last_updated = time.time()
            self.last_error = None  # Clear error on successful update
        
    def set_nifty50_updating(self, error: str = None):
        """Set Nifty50 state to updating and optionally set error."""
        self._set_state('nifty50_state', STATE_UPDATING)
        if error:
            self.last_error = error

    def set_nifty50_updated(self, error: str = None):
        """Mark Nifty 50 data as updated and update timestamp.
        
        Args:
            error: Optional error message. If provided, state is set to ERROR.
        """
        if error:
            self.last_error = error
            self._set_state('nifty50_state', STATE_ERROR)
        else:
            self._set_state('nifty50_state', STATE_UPDATED)
            self.nifty50_last_updated = time.time()
            # Don't clear last_error here as it might be from portfolio fetch
    
    def is_any_running(self) -> bool:
        """Check if any operation is currently updating."""
        return self.portfolio_state == STATE_UPDATING or self.nifty50_state == STATE_UPDATING
    
    def clear_error(self):
        """Clear the last error message."""
        self.last_error = None
        self._notify_change()


def format_timestamp(ts: float) -> str:
    """Format Unix timestamp to readable format."""
    if ts is None:
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def is_market_open_ist() -> bool:
    """Check if equity market is currently open.
    
    Market hours: 9:00 AM - 4:30 PM IST, Monday-Friday
    """
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)
    
    # Check if weekend
    if now.weekday() >= WEEKEND_SATURDAY:
        return False
    
    # Define market hours
    market_open = now.replace(
        hour=MARKET_OPEN_HOUR,
        minute=MARKET_OPEN_MINUTE,
        second=0,
        microsecond=0
    )
    market_close = now.replace(
        hour=MARKET_CLOSE_HOUR,
        minute=MARKET_CLOSE_MINUTE,
        second=0,
        microsecond=0
    )
    
    return market_open <= now <= market_close


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Error loading config: %s", e)
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
