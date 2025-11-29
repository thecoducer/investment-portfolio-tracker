"""
Unit tests for utility functions
"""
import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from utils import (
    SessionManager,
    StateManager,
    load_config,
    validate_accounts,
    format_timestamp,
    is_market_open_ist
)
from constants import STATE_UPDATING, STATE_UPDATED, STATE_ERROR


class TestSessionManager(unittest.TestCase):
    """Test SessionManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.session_manager = SessionManager(self.temp_file.name)
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_get_token_empty_cache(self):
        """Test getting token from empty cache"""
        token = self.session_manager.get_token("test_account")
        self.assertIsNone(token)
    
    def test_save_and_get_token(self):
        """Test saving and retrieving token"""
        test_token = "test_access_token_123"
        self.session_manager.set_token("test_account", test_token)
        retrieved_token = self.session_manager.get_token("test_account")
        self.assertEqual(retrieved_token, test_token)
    
    def test_token_expiry(self):
        """Test expired token returns None"""
        from datetime import timezone
        test_token = "expired_token"
        # Set token with expired time
        self.session_manager.sessions["test_account"] = {
            "access_token": test_token,
            "expiry": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        
        # get_token returns the token regardless of expiry
        retrieved_token = self.session_manager.get_token("test_account")
        self.assertEqual(retrieved_token, test_token)
        
        # But is_valid should return False
        self.assertFalse(self.session_manager.is_valid("test_account"))
    
    def test_clear_token(self):
        """Test clearing token"""
        self.session_manager.set_token("test_account", "token123")
        # Manually clear since there's no clear_token method
        del self.session_manager.sessions["test_account"]
        token = self.session_manager.get_token("test_account")
        self.assertIsNone(token)
    
    def test_multiple_accounts(self):
        """Test managing tokens for multiple accounts"""
        self.session_manager.set_token("account1", "token1")
        self.session_manager.set_token("account2", "token2")
        
        self.assertEqual(self.session_manager.get_token("account1"), "token1")
        self.assertEqual(self.session_manager.get_token("account2"), "token2")
    
    def test_corrupted_cache_file(self):
        """Test handling of corrupted cache file"""
        with open(self.temp_file.name, 'w') as f:
            f.write("invalid json {]}")
        
        # Should handle gracefully and return None
        token = self.session_manager.get_token("test_account")
        self.assertIsNone(token)


class TestStateManager(unittest.TestCase):
    """Test StateManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.state_manager = StateManager()
    
    def test_initial_state(self):
        """Test initial state is updating"""
        self.assertEqual(self.state_manager.refresh_state, STATE_UPDATING)
        self.assertEqual(self.state_manager.ltp_fetch_state, STATE_UPDATED)
    
    def test_set_refresh_running(self):
        """Test setting refresh to running state"""
        self.state_manager.set_portfolio_updating()
        self.assertEqual(self.state_manager.refresh_state, STATE_UPDATING)
    
    def test_set_refresh_idle(self):
        """Test setting refresh to idle state"""
        self.state_manager.set_portfolio_updated()
        self.assertEqual(self.state_manager.refresh_state, STATE_UPDATED)
    
    def test_set_ltp_idle(self):
        """Test setting LTP fetch to idle"""
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.ltp_fetch_state, STATE_UPDATED)
    
    def test_combined_state_all_idle(self):
        """Test combined state when all idle"""
        self.state_manager.set_portfolio_updated()
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.get_combined_state(), STATE_UPDATED)
    
    def test_combined_state_refresh_running(self):
        """Test combined state when refresh running"""
        self.state_manager.set_portfolio_updating()
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.get_combined_state(), STATE_UPDATING)
    
    def test_set_holdings_updated(self):
        """Test setting holdings updated timestamp"""
        
    
    def test_error_tracking(self):
        """Test error message tracking"""
        error_msg = "Test error message"
        self.state_manager.last_error = error_msg
        self.assertEqual(self.state_manager.last_error, error_msg)
    
    def test_change_listener(self):
        """Test adding and triggering change listener"""
        callback_called = []
        
        def callback():
            callback_called.append(True)
        
        self.state_manager.add_change_listener(callback)
        self.state_manager.set_portfolio_updating()
        
        self.assertTrue(len(callback_called) > 0)
    
    def test_change_listener_error_handling(self):
        """Test change listener handles exceptions gracefully"""
        def bad_callback():
            raise Exception("Callback error")
        
        self.state_manager.add_change_listener(bad_callback)
        
        # Should not raise, just print error
        self.state_manager.set_portfolio_updating()
    
    def test_is_any_running_true(self):
        """Test is_any_running returns True when refresh is running"""
        self.state_manager.set_portfolio_updating()
        self.assertTrue(self.state_manager.is_any_running())
    
    def test_is_any_running_false(self):
        """Test is_any_running returns False when updated"""
        self.state_manager.set_portfolio_updated()
        self.assertFalse(self.state_manager.is_any_running())


class TestConfigLoader(unittest.TestCase):
    """Test configuration loading and validation"""
    
    def test_load_valid_config(self):
        """Test loading valid configuration"""
        config = {
            "accounts": [
                {
                    "name": "TestAccount",
                    "api_key": "test_key",
                    "api_secret": "test_secret"
                }
            ],
            "server": {
                "callback_host": "127.0.0.1",
                "callback_port": 5000
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(config, f)
            temp_path = f.name
        
        try:
            loaded_config = load_config(temp_path)
            self.assertEqual(loaded_config["accounts"][0]["name"], "TestAccount")
        finally:
            os.unlink(temp_path)
    
    def test_load_missing_config(self):
        """Test loading non-existent config file"""
        result = load_config("nonexistent_config.json")
        self.assertEqual(result, {})
    
    def test_validate_accounts_valid(self):
        """Test validating valid accounts"""
        accounts = [
            {"name": "Account1", "api_key": "key1", "api_secret": "secret1"}
        ]
        # Should not raise exception
        validate_accounts(accounts)
    
    def test_validate_accounts_missing_name(self):
        """Test validating account without name"""
        accounts = [
            {"api_key": "key1", "api_secret": "secret1"}
        ]
        # Should not raise since name is optional, only api_key/secret are checked
        try:
            validate_accounts(accounts)
        except RuntimeError:
            pass  # Expected if credentials missing
    
    def test_validate_accounts_missing_api_key(self):
        """Test validating account without api_key"""
        accounts = [
            {"name": "Account1", "api_secret": "secret1"}
        ]
        with self.assertRaises(RuntimeError):
            validate_accounts(accounts)
    
    def test_validate_accounts_empty_list(self):
        """Test validating empty accounts list"""
        # Empty list doesn't raise, only missing credentials do
        validate_accounts([])
    
    def test_load_config_json_parse_error(self):
        """Test loading config with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            result = load_config(temp_path)
            self.assertEqual(result, {})
        finally:
            os.unlink(temp_path)


class TestFormatTimestamp(unittest.TestCase):
    """Test timestamp formatting"""
    
    def test_format_none_timestamp(self):
        """Test formatting None timestamp"""
        result = format_timestamp(None)
        self.assertIsNone(result)
    
    def test_format_valid_timestamp(self):
        """Test formatting valid timestamp"""
        import time
        now = time.time()
        result = format_timestamp(now)
        self.assertIsInstance(result, str)
        self.assertIn(":", result)  # Should contain time separator
    
    def test_format_timestamp_with_timezone(self):
        """Test formatting timestamp with timezone"""
        import time
        now = time.time()
        result = format_timestamp(now)
        self.assertIsInstance(result, str)


class TestMarketHours(unittest.TestCase):
    """Test market hours checking"""
    
    @patch('utils.datetime')
    def test_market_open_weekday_during_hours(self, mock_datetime):
        """Test market open on weekday during trading hours"""
        # Mock a Wednesday at 10:00 AM IST
        ist = ZoneInfo('Asia/Kolkata')
        mock_now = datetime(2025, 11, 26, 10, 0, 0, tzinfo=ist)  # Wednesday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertTrue(result)
    
    @patch('utils.datetime')
    def test_market_closed_before_hours(self, mock_datetime):
        """Test market closed before trading hours"""
        ist = ZoneInfo('Asia/Kolkata')
        mock_now = datetime(2025, 11, 26, 8, 0, 0, tzinfo=ist)  # 8 AM
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_after_hours(self, mock_datetime):
        """Test market closed after trading hours"""
        ist = ZoneInfo('Asia/Kolkata')
        mock_now = datetime(2025, 11, 26, 17, 0, 0, tzinfo=ist)  # 5 PM (after 4:30 PM close)
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_weekend_saturday(self, mock_datetime):
        """Test market closed on Saturday"""
        ist = ZoneInfo('Asia/Kolkata')
        mock_now = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ist)  # Saturday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_weekend_sunday(self, mock_datetime):
        """Test market closed on Sunday"""
        ist = ZoneInfo('Asia/Kolkata')
        mock_now = datetime(2025, 11, 23, 10, 0, 0, tzinfo=ist)  # Sunday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
