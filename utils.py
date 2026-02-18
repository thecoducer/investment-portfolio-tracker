"""
Utility functions for session management, market operations, and common patterns.
"""
import json
import os
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from base64 import urlsafe_b64encode
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
    
    def invalidate(self, account_name: str):
        """Invalidate (remove) the session for an account."""
        if account_name in self.sessions:
            del self.sessions[account_name]
            logger.info("Invalidated session for account: %s", account_name)
            self.save()
    
    def get_validity(self, all_accounts: List[str] = None) -> Dict[str, bool]:
        """Get validity status for all accounts.
        
        Args:
            all_accounts: Optional list of all account names from config.
                         If provided, ensures all accounts are included in result.
        
        Returns:
            Dict mapping account name to validity status (True if valid, False otherwise)
        """
        if all_accounts:
            # Include all configured accounts, not just those with cached sessions
            return {name: self.is_valid(name) for name in all_accounts}
        else:
            # Backward compatibility: only return accounts with cached sessions
            return {name: self.is_valid(name) for name in self.sessions.keys()}


class StateManager:
    """Manages application state with thread safety."""
    
    # State type names for dynamic attribute access
    STATE_TYPES = ('portfolio', 'nifty50', 'physical_gold', 'fixed_deposits')
    
    def __init__(self):
        # Initialize all state types dynamically
        for state_type in self.STATE_TYPES:
            setattr(self, f'{state_type}_state', None)
            setattr(self, f'{state_type}_last_updated', None)
        
        self.last_error: str = None
        self.waiting_for_login = False
        self._change_listeners = []
    
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
    
    def _set_updating(self, state_type: str, error: str = None):
        """Generic method to set any state type to updating."""
        setattr(self, f'{state_type}_state', STATE_UPDATING)
        if error:
            self.last_error = error
        self._notify_change()
    
    def _set_updated(self, state_type: str, error: str = None, clear_global_error: bool = False):
        """Generic method to mark any state type as updated.
        
        Args:
            state_type: Type of state (portfolio, nifty50, etc.)
            error: Optional error message. If provided, state is set to ERROR.
            clear_global_error: If True and no error, clear last_error.
        """
        if error:
            self.last_error = error
            setattr(self, f'{state_type}_state', STATE_ERROR)
        else:
            setattr(self, f'{state_type}_last_updated', time.time())
            if clear_global_error:
                self.last_error = None
            setattr(self, f'{state_type}_state', STATE_UPDATED)
        self._notify_change()
    
    # Portfolio-specific methods (has additional login flag logic)
    def set_portfolio_updating(self, error: str = None):
        self._set_updating('portfolio', error)
    
    def set_portfolio_updated(self, error: str = None):
        self.waiting_for_login = False
        self._set_updated('portfolio', error, clear_global_error=True)
    
    # Generic setters for other state types
    def set_nifty50_updating(self, error: str = None):
        self._set_updating('nifty50', error)

    def set_nifty50_updated(self, error: str = None):
        self._set_updated('nifty50', error)
    
    def set_physical_gold_updating(self, error: str = None):
        self._set_updating('physical_gold', error)

    def set_physical_gold_updated(self, error: str = None):
        self._set_updated('physical_gold', error)
    
    def set_fixed_deposits_updating(self, error: str = None):
        self._set_updating('fixed_deposits', error)

    def set_fixed_deposits_updated(self, error: str = None):
        self._set_updated('fixed_deposits', error)
    
    def is_any_running(self) -> bool:
        """Check if any operation is currently updating."""
        return any(
            getattr(self, f'{st}_state') == STATE_UPDATING 
            for st in self.STATE_TYPES
        )
    
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
