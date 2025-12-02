"""
Authentication and session management for Zerodha KiteConnect.
"""
import os
import webbrowser
import threading
from typing import Dict, Any, List, Tuple, Optional

from kiteconnect import KiteConnect
from logging_config import logger


class AuthenticationManager:
    """Handles authentication flow with KiteConnect API.
    
    Supports three authentication strategies:
    1. Cached token (fastest, if valid)
    2. Token renewal (if cached token expired but renewable)
    3. Full OAuth login (if above fail)
    """
    
    def __init__(self, session_manager, request_token_timeout: int = 180, state_manager=None):
        self.session_manager = session_manager
        self.request_token_timeout = request_token_timeout
        self.state_manager = state_manager
        self.request_token_holder = {"token": None}
        self.request_token_event = threading.Event()
        self.request_token_lock = threading.Lock()
    
    def set_request_token(self, token: str) -> None:
        """Set the request token from OAuth callback."""
        with self.request_token_lock:
            self.request_token_holder["token"] = token
            self.request_token_event.set()
    
    def _wait_for_request_token(self, account_name: str) -> str:
        """Wait for request token from OAuth callback.
        
        During the wait, periodically trigger state updates to keep frontend alive.
        """
        with self.request_token_lock:
            self.request_token_holder["token"] = None
            self.request_token_event.clear()
        
        # Wait with periodic heartbeats to keep UI alive
        wait_interval = 5  # Check every 5 seconds
        total_waited = 0
        
        while total_waited < self.request_token_timeout:
            if self.request_token_event.wait(timeout=wait_interval):
                # Token received
                break
            total_waited += wait_interval
            
            # Trigger state update to keep SSE connection alive
            if self.state_manager:
                self.state_manager._notify_change()
        else:
            # Timeout occurred
            raise TimeoutError(f"Timed out waiting for request_token for {account_name}")
        
        with self.request_token_lock:
            req_token = self.request_token_holder.get("token")
        
        if not req_token:
            raise RuntimeError("request_token was not provided")
        
        return req_token
    
    def _validate_token_with_api_call(self, kite: KiteConnect, account_name: str) -> bool:
        """Validate token by making a test API call. Returns True if valid."""
        try:
            kite.profile()
            return True
        except Exception as e:
            logger.exception("Token validation failed for %s: %s", account_name, e)
            return False
    
    def _try_cached_token(self, kite: KiteConnect, account_name: str) -> bool:
        """Try to use cached token. Returns True if successful."""
        if not self.session_manager.is_valid(account_name):
            return False
        logger.info("Using cached token for %s", account_name)
        kite.set_access_token(self.session_manager.get_token(account_name))
        return self._validate_token_with_api_call(kite, account_name)
    
    def _store_token(self, kite: KiteConnect, account_name: str, access_token: str) -> None:
        """Store and apply access token to KiteConnect instance."""
        kite.set_access_token(access_token)
        self.session_manager.set_token(account_name, access_token)
        self.session_manager.save()
    
    def _try_renew_token(self, kite: KiteConnect, account_name: str, api_secret: str) -> bool:
        """Try to renew expired token. Returns True if successful."""
        logger.info("Attempting to renew session for %s...", account_name)
        try:
            old_token = self.session_manager.get_token(account_name)
            
            # Skip renewal if no token exists
            if not old_token:
                logger.info("No token found for %s, skipping renewal", account_name)
                return False
            
            renewed_session = kite.renew_access_token(old_token, api_secret)
            new_access_token = renewed_session.get("access_token")
            
            if new_access_token:
                logger.info("Successfully renewed session for %s", account_name)
                self._store_token(kite, account_name, new_access_token)
                return True
        except Exception as e:
            logger.exception("Session renewal failed for %s: %s", account_name, e)
        
        return False
    
    def _perform_full_login(self, kite: KiteConnect, account_name: str, api_secret: str) -> str:
        """Perform full OAuth login flow. Returns access token."""
        logger.info("Initiating login flow for %s", account_name)
        
        # Mark that we're waiting for login
        if self.state_manager:
            self.state_manager.waiting_for_login = True
            self.state_manager._notify_change()
        
        webbrowser.open(kite.login_url())
        
        req_token = self._wait_for_request_token(account_name)
        session_data = kite.generate_session(req_token, api_secret=api_secret)
        access_token = session_data.get("access_token")
        
        if not access_token:
            raise RuntimeError("Failed to obtain access_token")
        
        self._store_token(kite, account_name, access_token)
        logger.info("Successfully authenticated %s", account_name)
        
        return access_token
    
    def authenticate(self, account_config: Dict[str, Any], force_login: bool = False) -> KiteConnect:
        """Authenticate and return KiteConnect instance.
        
        Tries authentication strategies in order:
        1. Cached token (unless force_login=True)
        2. Token renewal (if cached exists but expired)
        3. Full OAuth login
        
        Args:
            account_config: Account configuration with api_key, api_secret
            force_login: Force new login even if cached token exists
        
        Returns:
            Authenticated KiteConnect instance
        """
        account_name = account_config["name"]
        api_key = account_config["api_key"]
        api_secret = account_config["api_secret"]
        
        kite = KiteConnect(api_key=api_key)
        
        # Strategy 1: Try cached token (unless forced login)
        if not force_login and self._try_cached_token(kite, account_name):
            return kite
        
        # Strategy 2: Try token renewal
        if not force_login and self._try_renew_token(kite, account_name, api_secret):
            return kite
        
        # Strategy 3: Fall back to full login
        self._perform_full_login(kite, account_name, api_secret)
        return kite
