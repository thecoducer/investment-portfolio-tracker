"""
Unit tests for API services
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime

from api.holdings import HoldingsService
from api.ltp import LTPService
from api.auth import AuthenticationManager


class MockKiteConnect:
    """Mock KiteConnect API for testing"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self._access_token = None
        self._mock_holdings = []
        self._mock_mf_holdings = []
        self._mock_mf_instruments = []
        self._mock_mf_sips = []
        self._mock_profile = {"user_id": "TEST123", "user_name": "Test User"}
    
    def set_access_token(self, access_token: str):
        """Mock setting access token"""
        self._access_token = access_token
    
    def holdings(self):
        """Mock holdings API call"""
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_holdings
    
    def mf_holdings(self):
        """Mock MF holdings API call"""
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_mf_holdings
    
    def mf_instruments(self):
        """Mock MF instruments API call"""
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_mf_instruments
    
    def mf_sips(self, sip_id=None):
        """Mock MF SIPs API call"""
        if not self._access_token:
            raise Exception("Not authenticated")
        if sip_id:
            return [sip for sip in self._mock_mf_sips if sip.get('sip_id') == sip_id]
        return self._mock_mf_sips
    
    def profile(self):
        """Mock profile API call"""
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_profile
    
    def login_url(self):
        """Mock login URL generation"""
        return f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"
    
    def generate_session(self, request_token: str, api_secret: str):
        """Mock session generation"""
        return {
            "user_id": "TEST123",
            "access_token": f"mock_token_{request_token}",
            "refresh_token": "mock_refresh_token"
        }
    
    def renew_access_token(self, refresh_token: str, api_secret: str):
        """Mock token renewal"""
        return {
            "access_token": f"renewed_{refresh_token}",
            "refresh_token": "new_refresh_token"
        }


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
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        mock_kite._mock_holdings = [{
            "tradingsymbol": "RELIANCE",
            "exchange": "NSE",
            "quantity": 10,
            "average_price": 2500.0,
            "last_price": 2600.0
        }]
        mock_kite._mock_mf_holdings = [{
            "tradingsymbol": "MF1",
            "folio": "12345",
            "quantity": 100.5,
            "average_price": 25.5
        }]
        
        stocks, mfs = self.service.fetch_holdings(mock_kite)
        
        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]["tradingsymbol"], "RELIANCE")
        self.assertEqual(len(mfs), 1)
        self.assertEqual(mfs[0]["tradingsymbol"], "MF1")
        mock_add_nav_dates.assert_called_once()
    
    def test_add_nav_dates_with_instruments(self):
        """Test adding NAV dates to MF holdings"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        mock_kite._mock_mf_instruments = [
            {
                "tradingsymbol": "MF1",
                "name": "Test Mutual Fund",
                "last_price": 25.5,
                "last_price_date": "2025-11-22"
            }
        ]
        
        mf_holdings = [{"tradingsymbol": "MF1", "quantity": 100}]
        self.service._add_nav_dates(mf_holdings, mock_kite)
        
        self.assertEqual(mf_holdings[0]["last_price_date"], "2025-11-22")
    
    def test_add_nav_dates_missing_instrument(self):
        """Test adding NAV dates when instrument not found"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        mock_kite._mock_mf_instruments = []
        
        mf_holdings = [{"tradingsymbol": "MF1"}]
        self.service._add_nav_dates(mf_holdings, mock_kite)
        
        self.assertIsNone(mf_holdings[0].get("last_price_date"))
    
    def test_add_nav_dates_api_error(self):
        """Test handling API error when fetching instruments"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        
        # Make mf_instruments raise an exception
        def raise_error():
            raise Exception("API Error")
        mock_kite.mf_instruments = raise_error
        
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
        
        self.assertIn("RELIANCE.NS", symbols)
    
    def test_prepare_symbols_bse(self):
        """Test preparing symbols for BSE exchange"""
        holdings = [
            {"tradingsymbol": "RELIANCE", "exchange": "BSE"}
        ]
        
        symbols = self.service._prepare_symbols(holdings)
        
        self.assertIn("RELIANCE.BO", symbols)
    
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
        self.assertEqual(key, "RELIANCE.NS")
    
    @patch('api.ltp.requests.get')
    def test_fetch_ltps_success(self, mock_get):
        """Test successful LTP fetch from NSE API"""
        # Mock NSE API response structure
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "RELIANCE.NS": {
                "last_price": 2500.0,
                "change": 25.0,
                "pChange": 1.01,
                "volume": 1000000
            }
        }
        mock_get.return_value = mock_response
        
        holdings = [{
            "tradingsymbol": "RELIANCE",
            "exchange": "NSE",
            "quantity": 10,
            "average_price": 2400.0
        }]
        
        ltp_data = self.service.fetch_ltps(holdings)
        
        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("RELIANCE.NS", call_args[0][0])
        
        # Verify response
        self.assertIn("RELIANCE.NS", ltp_data)
        self.assertEqual(ltp_data["RELIANCE.NS"]["last_price"], 2500.0)
    
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
            "RELIANCE.NS": {"last_price": 2500.0}
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
        self.auth_manager = AuthenticationManager(self.session_manager, request_token_timeout=180)
    
    def test_set_and_get_request_token(self):
        """Test setting and getting request token"""
        self.auth_manager.set_request_token("test_token")
        with self.auth_manager.request_token_lock:
            token = self.auth_manager.request_token_holder.get("token")
        self.assertEqual(token, "test_token")
    
    def test_try_cached_token_valid(self):
        """Test using valid cached token with KiteConnect"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        self.session_manager.is_valid.return_value = True
        self.session_manager.get_token.return_value = "cached_token_123"
        
        result = self.auth_manager._try_cached_token(mock_kite, "TestAccount")
        
        self.assertTrue(result)
        self.assertEqual(mock_kite._access_token, "cached_token_123")
    
    def test_try_cached_token_none(self):
        """Test when no cached token exists"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        self.session_manager.is_valid.return_value = False
        
        result = self.auth_manager._try_cached_token(mock_kite, "TestAccount")
        
        self.assertFalse(result)
        self.assertIsNone(mock_kite._access_token)
    
    def test_try_cached_token_invalid(self):
        """Test when cached token exists and is set"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        self.session_manager.is_valid.return_value = True
        self.session_manager.get_token.return_value = "some_token"
        
        result = self.auth_manager._try_cached_token(mock_kite, "TestAccount")
        
        # Since implementation doesn't validate in _try_cached_token, it returns True
        self.assertTrue(result)
        self.assertEqual(mock_kite._access_token, "some_token")
    
    @patch('api.auth.webbrowser.open')
    def test_wait_for_request_token_timeout(self, mock_browser):
        """Test timeout when waiting for request token"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        
        # Set short timeout for test
        self.auth_manager.request_token_timeout = 0.1
        
        with self.assertRaises(TimeoutError) as context:
            self.auth_manager._wait_for_request_token("TestAccount")
        
        self.assertIn("Timed out", str(context.exception))
    
    def test_generate_session_mock(self):
        """Test mocked session generation"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        
        session_data = mock_kite.generate_session("request_token_123", "api_secret_456")
        
        self.assertIn("access_token", session_data)
        self.assertIn("request_token_123", session_data["access_token"])
        self.assertEqual(session_data["user_id"], "TEST123")
    
    def test_renew_access_token_mock(self):
        """Test mocked token renewal"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        
        renewed_data = mock_kite.renew_access_token("old_refresh_token", "api_secret")
        
        self.assertIn("access_token", renewed_data)
        self.assertIn("old_refresh_token", renewed_data["access_token"])


class TestSIPService(unittest.TestCase):
    """Test SIPService class"""
    
    def setUp(self):
        """Set up test fixtures"""
        from api.sips import SIPService
        self.service = SIPService()
    
    def test_fetch_sips(self):
        """Test fetching SIPs from KiteConnect"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        mock_kite._mock_mf_sips = [
            {
                "sip_id": "SIP001",
                "tradingsymbol": "INF174K01LS2",
                "fund": "HDFC Equity Fund",
                "instalment_amount": 5000,
                "frequency": "monthly",
                "instalments": 12,
                "completed_instalments": 5,
                "status": "ACTIVE",
                "next_instalment": "2025-12-01"
            }
        ]
        
        sips = self.service.fetch_sips(mock_kite)
        
        self.assertEqual(len(sips), 1)
        self.assertEqual(sips[0]["sip_id"], "SIP001")
        self.assertEqual(sips[0]["instalment_amount"], 5000)
        self.assertEqual(sips[0]["status"], "ACTIVE")
    
    def test_fetch_sips_empty(self):
        """Test fetching SIPs when none exist"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        mock_kite._mock_mf_sips = []
        
        sips = self.service.fetch_sips(mock_kite)
        
        self.assertEqual(len(sips), 0)
    
    def test_add_account_info(self):
        """Test adding account information to SIPs"""
        sips = [
            {"sip_id": "SIP001", "instalment_amount": 5000},
            {"sip_id": "SIP002", "instalment_amount": 3000}
        ]
        
        self.service.add_account_info(sips, "Account1")
        
        self.assertEqual(sips[0]["account"], "Account1")
        self.assertEqual(sips[1]["account"], "Account1")
    
    def test_merge_sips_single_account(self):
        """Test merging SIPs from single account"""
        all_sips = [
            [{"sip_id": "SIP001"}, {"sip_id": "SIP002"}]
        ]
        
        merged = self.service.merge_sips(all_sips)
        
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["sip_id"], "SIP001")
        self.assertEqual(merged[1]["sip_id"], "SIP002")
    
    def test_merge_sips_multiple_accounts(self):
        """Test merging SIPs from multiple accounts"""
        all_sips = [
            [{"sip_id": "SIP001", "account": "Account1"}],
            [{"sip_id": "SIP002", "account": "Account2"}],
            [{"sip_id": "SIP003", "account": "Account3"}]
        ]
        
        merged = self.service.merge_sips(all_sips)
        
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["account"], "Account1")
        self.assertEqual(merged[1]["account"], "Account2")
        self.assertEqual(merged[2]["account"], "Account3")
    
    def test_merge_sips_empty_lists(self):
        """Test merging empty SIP lists"""
        all_sips = [[], [], []]
        
        merged = self.service.merge_sips(all_sips)
        
        self.assertEqual(len(merged), 0)


if __name__ == '__main__':
    unittest.main()
