"""
Authentication and session management for Zerodha KiteConnect.
"""
import os
import webbrowser
import threading
from typing import Dict, Any, List, Tuple, Optional

from kiteconnect import KiteConnect


class AuthenticationManager:
    """Handles authentication flow with KiteConnect API."""
    
    def __init__(self, session_manager, request_token_timeout: int = 180):
        self.session_manager = session_manager
        self.request_token_timeout = request_token_timeout
        self.request_token_holder = {"token": None}
        self.request_token_event = threading.Event()
        self.request_token_lock = threading.Lock()
    
    def set_request_token(self, token: str) -> None:
        """Set the request token from OAuth callback."""
        with self.request_token_lock:
            self.request_token_holder["token"] = token
            self.request_token_event.set()
    
    def _wait_for_request_token(self, account_name: str) -> str:
        """Wait for request token from OAuth callback."""
        with self.request_token_lock:
            self.request_token_holder["token"] = None
            self.request_token_event.clear()
        
        if not self.request_token_event.wait(timeout=self.request_token_timeout):
            raise TimeoutError(f"Timed out waiting for request_token for {account_name}")
        
        with self.request_token_lock:
            req_token = self.request_token_holder.get("token")
        
        if not req_token:
            raise RuntimeError("request_token was not provided")
        
        return req_token
    
    def _try_cached_token(self, kite: KiteConnect, account_name: str) -> bool:
        """Try to use cached token. Returns True if successful."""
        if not self.session_manager.is_valid(account_name):
            return False
        
        print(f"Using cached token for {account_name}")
        kite.set_access_token(self.session_manager.get_token(account_name))
        return True
    
    def _try_renew_token(self, kite: KiteConnect, account_name: str, api_secret: str) -> bool:
        """Try to renew expired token. Returns True if successful."""
        print(f"Attempting to renew session for {account_name}...")
        try:
            old_token = self.session_manager.get_token(account_name)
            renewed_session = kite.renew_access_token(old_token, api_secret)
            new_access_token = renewed_session.get("access_token")
            
            if new_access_token:
                print(f"Successfully renewed session for {account_name}")
                kite.set_access_token(new_access_token)
                self.session_manager.set_token(account_name, new_access_token)
                self.session_manager.save()
                return True
        except Exception as e:
            print(f"Session renewal failed for {account_name}: {e}")
        
        return False
    
    def _perform_full_login(self, kite: KiteConnect, account_name: str, api_secret: str) -> str:
        """Perform full OAuth login flow. Returns access token."""
        print(f"Initiating login flow for {account_name}")
        webbrowser.open(kite.login_url())
        
        req_token = self._wait_for_request_token(account_name)
        session_data = kite.generate_session(req_token, api_secret=api_secret)
        access_token = session_data.get("access_token")
        
        if not access_token:
            raise RuntimeError("Failed to obtain access_token")
        
        kite.set_access_token(access_token)
        self.session_manager.set_token(account_name, access_token)
        self.session_manager.save()
        print(f"Successfully authenticated {account_name}")
        
        return access_token
    
    def authenticate(self, account_config: Dict[str, Any], force_login: bool = False) -> KiteConnect:
        """
        Authenticate and return KiteConnect instance.
        
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
        
        # Try cached token first
        if not force_login and self._try_cached_token(kite, account_name):
            try:
                # Validate token with a test call
                kite.profile()
                return kite
            except Exception as e:
                print(f"Cached token failed for {account_name}: {e}")
                # Try renewal before full login
                if self._try_renew_token(kite, account_name, api_secret):
                    return kite
        
        # Fall back to full login
        self._perform_full_login(kite, account_name, api_secret)
        return kite
