"""
Unit tests for API services
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from api.holdings import HoldingsService
from api.ltp import LTPService
from api.auth import AuthenticationManager


class TestHoldingsService(unittest.TestCase):
    """Test HoldingsService class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = HoldingsService()
    
    def test_add_account_info(self):
        """Test adding account information to holdings"""
        holdings = [
            {"quantity": 10, "average_price": 100.0},
            {"quantity": 5, "average_price": 200.0}
        ]
        
        self.service.add_account_info(holdings, "TestAccount")
        
        self.assertEqual(holdings[0]["account"], "TestAccount")
        self.assertEqual(holdings[0]["invested"], 1000.0)
        self.assertEqual(holdings[1]["invested"], 1000.0)
    
    def test_add_account_info_missing_fields(self):
        """Test adding account info with missing fields"""
        holdings = [
            {},  # No quantity or average_price
        ]
        
        self.service.add_account_info(holdings, "TestAccount")
        
        self.assertEqual(holdings[0]["account"], "TestAccount")
        self.assertEqual(holdings[0]["invested"], 0.0)
    
    def test_merge_holdings_single_account(self):
        """Test merging holdings from single account"""
        stock_holdings = [[{"symbol": "RELIANCE"}]]
        mf_holdings = [[{"symbol": "MF1"}]]
        
        merged_stocks, merged_mfs = self.service.merge_holdings(stock_holdings, mf_holdings)
        
        self.assertEqual(len(merged_stocks), 1)
        self.assertEqual(len(merged_mfs), 1)
    
    def test_merge_holdings_multiple_accounts(self):
        """Test merging holdings from multiple accounts"""
        stock_holdings = [
            [{"symbol": "RELIANCE"}],
            [{"symbol": "TCS"}]
        ]
        mf_holdings = [
            [{"symbol": "MF1"}],
            [{"symbol": "MF2"}]
        ]
        
        merged_stocks, merged_mfs = self.service.merge_holdings(stock_holdings, mf_holdings)
        
        self.assertEqual(len(merged_stocks), 2)
        self.assertEqual(len(merged_mfs), 2)
    
    def test_merge_holdings_empty_lists(self):
        """Test merging empty holdings lists"""
        merged_stocks, merged_mfs = self.service.merge_holdings([], [])
        
        self.assertEqual(len(merged_stocks), 0)
        self.assertEqual(len(merged_mfs), 0)
    
    @patch('api.holdings.HoldingsService._add_nav_dates')
    def test_fetch_holdings(self, mock_add_nav_dates):
        """Test fetching holdings from KiteConnect"""
        mock_kite = Mock()
        mock_kite.holdings.return_value = [{"tradingsymbol": "RELIANCE"}]
        mock_kite.mf_holdings.return_value = [{"tradingsymbol": "MF1"}]
        
        stocks, mfs = self.service.fetch_holdings(mock_kite)
        
        self.assertEqual(len(stocks), 1)
        self.assertEqual(len(mfs), 1)
        mock_add_nav_dates.assert_called_once()
    
    def test_add_nav_dates_with_instruments(self):
        """Test adding NAV dates to MF holdings"""
        mock_kite = Mock()
        mock_kite.mf_instruments.return_value = [
            {"tradingsymbol": "MF1", "last_price_date": "2025-11-22"}
        ]
        
        mf_holdings = [{"tradingsymbol": "MF1"}]
        self.service._add_nav_dates(mf_holdings, mock_kite)
        
        self.assertEqual(mf_holdings[0]["last_price_date"], "2025-11-22")
    
    def test_add_nav_dates_missing_instrument(self):
        """Test adding NAV dates when instrument not found"""
        mock_kite = Mock()
        mock_kite.mf_instruments.return_value = []
        
        mf_holdings = [{"tradingsymbol": "MF1"}]
        self.service._add_nav_dates(mf_holdings, mock_kite)
        
        self.assertIsNone(mf_holdings[0].get("last_price_date"))
    
    def test_add_nav_dates_api_error(self):
        """Test handling API error when fetching instruments"""
        mock_kite = Mock()
        mock_kite.mf_instruments.side_effect = Exception("API Error")
        
        mf_holdings = [{"tradingsymbol": "MF1"}]
        # Should handle gracefully without raising
        self.service._add_nav_dates(mf_holdings, mock_kite)
        
        self.assertIsNone(mf_holdings[0].get("last_price_date"))


class TestLTPService(unittest.TestCase):
    """Test LTPService class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = LTPService()
    
    def test_prepare_symbols_nse(self):
        """Test preparing symbols for NSE exchange"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "NSE"}
        ]
        
        symbols = self.service._prepare_symbols(holdings)
        
        self.assertIn("RELIANCE:NSE", symbols)
    
    def test_prepare_symbols_bse(self):
        """Test preparing symbols for BSE exchange"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "BSE"}
        ]
        
        symbols = self.service._prepare_symbols(holdings)
        
        self.assertIn("RELIANCE:BSE", symbols)
    
    def test_prepare_symbols_unknown_exchange(self):
        """Test preparing symbols for unknown exchange"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "UNKNOWN"}
        ]
        
        symbols = self.service._prepare_symbols(holdings)
        
        self.assertIn("RELIANCE", symbols)
    
    def test_get_symbol_key(self):
        """Test getting symbol key for API"""
        key = self.service._get_symbol_key("RELIANCE", "NSE")
        self.assertEqual(key, "RELIANCE:NSE")
    
    @patch('api.ltp.requests.get')
    def test_fetch_ltps_success(self, mock_get):
        """Test successful LTP fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "RELIANCE:NSE": {"last_price": 2500.0}
        }
        mock_get.return_value = mock_response
        
        holdings = [{"tradingsymbol": "RELIANCE", "exchange": "NSE"}]
        ltp_data = self.service.fetch_ltps(holdings)
        
        self.assertIn("RELIANCE:NSE", ltp_data)
        self.assertEqual(ltp_data["RELIANCE:NSE"]["last_price"], 2500.0)
    
    @patch('api.ltp.requests.get')
    def test_fetch_ltps_http_error(self, mock_get):
        """Test LTP fetch with HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        holdings = [{"tradingsymbol": "RELIANCE", "exchange": "NSE"}]
        ltp_data = self.service.fetch_ltps(holdings)
        
        self.assertEqual(ltp_data, {})
    
    @patch('api.ltp.requests.get')
    def test_fetch_ltps_timeout(self, mock_get):
        """Test LTP fetch with timeout"""
        mock_get.side_effect = Exception("Timeout")
        
        holdings = [{"tradingsymbol": "RELIANCE", "exchange": "NSE"}]
        ltp_data = self.service.fetch_ltps(holdings)
        
        self.assertEqual(ltp_data, {})
    
    def test_update_holdings_with_ltp(self):
        """Test updating holdings with LTP data"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "NSE", "last_price": 0}
        ]
        ltp_data = {
            "RELIANCE:NSE": {"last_price": 2500.0}
        }
        
        self.service.update_holdings_with_ltp(holdings, ltp_data)
        
        self.assertEqual(holdings[0]["last_price"], 2500.0)
    
    def test_update_holdings_missing_ltp(self):
        """Test updating holdings when LTP not available"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "NSE", "last_price": 2400.0}
        ]
        ltp_data = {}
        
        self.service.update_holdings_with_ltp(holdings, ltp_data)
        
        # Should keep original value
        self.assertEqual(holdings[0]["last_price"], 2400.0)


class TestAuthenticationManager(unittest.TestCase):
    """Test AuthenticationManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_manager = Mock()
        self.auth_manager = AuthenticationManager(self.session_manager, timeout=180)
    
    def test_set_and_get_request_token(self):
        """Test setting and getting request token"""
        self.auth_manager.set_request_token("test_token")
        self.assertEqual(self.auth_manager.request_token, "test_token")
    
    def test_try_cached_token_valid(self):
        """Test using valid cached token"""
        mock_kite = Mock()
        self.session_manager.get_token.return_value = "cached_token"
        
        account_config = {"name": "TestAccount"}
        result = self.auth_manager._try_cached_token(mock_kite, account_config)
        
        self.assertTrue(result)
        mock_kite.set_access_token.assert_called_once_with("cached_token")
    
    def test_try_cached_token_none(self):
        """Test when no cached token exists"""
        mock_kite = Mock()
        self.session_manager.get_token.return_value = None
        
        account_config = {"name": "TestAccount"}
        result = self.auth_manager._try_cached_token(mock_kite, account_config)
        
        self.assertFalse(result)
    
    def test_try_cached_token_invalid(self):
        """Test when cached token is invalid"""
        mock_kite = Mock()
        mock_kite.profile.side_effect = Exception("Invalid token")
        self.session_manager.get_token.return_value = "invalid_token"
        
        account_config = {"name": "TestAccount"}
        result = self.auth_manager._try_cached_token(mock_kite, account_config)
        
        self.assertFalse(result)
        self.session_manager.clear_token.assert_called_once()


if __name__ == '__main__':
    unittest.main()
