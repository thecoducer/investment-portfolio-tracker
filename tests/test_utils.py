"""
Unit tests for utility functions
"""
import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytz

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
        self.session_manager.save_token("test_account", test_token)
        retrieved_token = self.session_manager.get_token("test_account")
        self.assertEqual(retrieved_token, test_token)
    
    def test_token_expiry(self):
        """Test expired token returns None"""
        test_token = "expired_token"
        self.session_manager.save_token("test_account", test_token, expires_in=1)
        
        # Simulate expiry by manually modifying cache
        cache = self.session_manager._load_cache()
        cache["test_account"]["expires_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
        self.session_manager._save_cache(cache)
        
        retrieved_token = self.session_manager.get_token("test_account")
        self.assertIsNone(retrieved_token)
    
    def test_clear_token(self):
        """Test clearing token"""
        self.session_manager.save_token("test_account", "token123")
        self.session_manager.clear_token("test_account")
        token = self.session_manager.get_token("test_account")
        self.assertIsNone(token)
    
    def test_multiple_accounts(self):
        """Test managing tokens for multiple accounts"""
        self.session_manager.save_token("account1", "token1")
        self.session_manager.save_token("account2", "token2")
        
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
        self.assertEqual(self.state_manager.state, STATE_UPDATING)
        self.assertEqual(self.state_manager.ltp_fetch_state, STATE_UPDATED)
    
    def test_set_refresh_running(self):
        """Test setting refresh to running state"""
        self.state_manager.set_refresh_running()
        self.assertEqual(self.state_manager.state, STATE_UPDATING)
    
    def test_set_refresh_idle(self):
        """Test setting refresh to idle state"""
        self.state_manager.set_refresh_idle()
        self.assertEqual(self.state_manager.state, STATE_UPDATED)
    
    def test_set_ltp_running(self):
        """Test setting LTP fetch to running"""
        self.state_manager.set_ltp_running()
        self.assertEqual(self.state_manager.ltp_fetch_state, STATE_UPDATING)
    
    def test_set_ltp_idle(self):
        """Test setting LTP fetch to idle"""
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.ltp_fetch_state, STATE_UPDATED)
    
    def test_combined_state_all_idle(self):
        """Test combined state when all idle"""
        self.state_manager.set_refresh_idle()
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.get_combined_state(), STATE_UPDATED)
    
    def test_combined_state_refresh_running(self):
        """Test combined state when refresh running"""
        self.state_manager.set_refresh_running()
        self.state_manager.set_ltp_idle()
        self.assertEqual(self.state_manager.get_combined_state(), STATE_UPDATING)
    
    def test_combined_state_ltp_running(self):
        """Test combined state when LTP running"""
        self.state_manager.set_refresh_idle()
        self.state_manager.set_ltp_running()
        self.assertEqual(self.state_manager.get_combined_state(), STATE_UPDATING)
    
    def test_set_holdings_updated(self):
        """Test setting holdings updated timestamp"""
        self.state_manager.set_holdings_updated()
        self.assertIsNotNone(self.state_manager.holdings_last_updated)
    
    def test_error_tracking(self):
        """Test error message tracking"""
        error_msg = "Test error message"
        self.state_manager.last_error = error_msg
        self.assertEqual(self.state_manager.last_error, error_msg)


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
        with self.assertRaises(SystemExit):
            load_config("nonexistent_config.json")
    
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
        with self.assertRaises(ValueError):
            validate_accounts(accounts)
    
    def test_validate_accounts_missing_api_key(self):
        """Test validating account without api_key"""
        accounts = [
            {"name": "Account1", "api_secret": "secret1"}
        ]
        with self.assertRaises(ValueError):
            validate_accounts(accounts)
    
    def test_validate_accounts_empty_list(self):
        """Test validating empty accounts list"""
        with self.assertRaises(ValueError):
            validate_accounts([])


class TestFormatTimestamp(unittest.TestCase):
    """Test timestamp formatting"""
    
    def test_format_none_timestamp(self):
        """Test formatting None timestamp"""
        result = format_timestamp(None)
        self.assertEqual(result, "")
    
    def test_format_valid_timestamp(self):
        """Test formatting valid timestamp"""
        now = datetime.now()
        result = format_timestamp(now)
        self.assertIsInstance(result, str)
        self.assertIn(":", result)  # Should contain time separator
    
    def test_format_timestamp_with_timezone(self):
        """Test formatting timestamp with timezone"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        result = format_timestamp(now)
        self.assertIsInstance(result, str)


class TestMarketHours(unittest.TestCase):
    """Test market hours checking"""
    
    @patch('utils.datetime')
    def test_market_open_weekday_during_hours(self, mock_datetime):
        """Test market open on weekday during trading hours"""
        # Mock a Wednesday at 10:00 AM IST
        ist = pytz.timezone('Asia/Kolkata')
        mock_now = ist.localize(datetime(2025, 11, 26, 10, 0, 0))  # Wednesday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertTrue(result)
    
    @patch('utils.datetime')
    def test_market_closed_before_hours(self, mock_datetime):
        """Test market closed before trading hours"""
        ist = pytz.timezone('Asia/Kolkata')
        mock_now = ist.localize(datetime(2025, 11, 26, 8, 0, 0))  # 8 AM
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_after_hours(self, mock_datetime):
        """Test market closed after trading hours"""
        ist = pytz.timezone('Asia/Kolkata')
        mock_now = ist.localize(datetime(2025, 11, 26, 16, 0, 0))  # 4 PM
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_weekend_saturday(self, mock_datetime):
        """Test market closed on Saturday"""
        ist = pytz.timezone('Asia/Kolkata')
        mock_now = ist.localize(datetime(2025, 11, 22, 10, 0, 0))  # Saturday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)
    
    @patch('utils.datetime')
    def test_market_closed_weekend_sunday(self, mock_datetime):
        """Test market closed on Sunday"""
        ist = pytz.timezone('Asia/Kolkata')
        mock_now = ist.localize(datetime(2025, 11, 23, 10, 0, 0))  # Sunday
        mock_datetime.now.return_value = mock_now
        
        result = is_market_open_ist()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
