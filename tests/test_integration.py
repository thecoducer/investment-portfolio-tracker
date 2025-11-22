"""
Integration tests for the portfolio tracker
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch, Mock

from api.holdings import HoldingsService
from utils import SessionManager, StateManager


class MockKiteConnect:
    """Mock KiteConnect API for integration testing"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self._access_token = None
        self._mock_holdings = []
        self._mock_mf_holdings = []
        self._mock_mf_instruments = []
        self._mock_mf_sips = []
    
    def set_access_token(self, access_token: str):
        self._access_token = access_token
    
    def holdings(self):
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_holdings
    
    def mf_holdings(self):
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_mf_holdings
    
    def mf_instruments(self):
        if not self._access_token:
            raise Exception("Not authenticated")
        return self._mock_mf_instruments
    
    def mf_sips(self, sip_id=None):
        if not self._access_token:
            raise Exception("Not authenticated")
        if sip_id:
            return [sip for sip in self._mock_mf_sips if sip.get('sip_id') == sip_id]
        return self._mock_mf_sips
    
    def profile(self):
        if not self._access_token:
            raise Exception("Not authenticated")
        return {"user_id": "TEST123", "user_name": "Test User"}


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.holdings_service = HoldingsService()
    
    def test_complete_holdings_flow(self):
        """Test complete flow: fetch, enrich, merge with mocked KiteConnect API"""
        # Create mock KiteConnect with realistic data
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_access_token")
        
        # Set up mock holdings data
        mock_kite._mock_holdings = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "NSE",
                "quantity": 10,
                "average_price": 2400.0,
                "last_price": 2500.0,
                "pnl": 1000.0
            },
            {
                "tradingsymbol": "TCS",
                "exchange": "NSE",
                "quantity": 5,
                "average_price": 3500.0,
                "last_price": 3600.0,
                "pnl": 500.0
            }
        ]
        
        mock_kite._mock_mf_holdings = []
        mock_kite._mock_mf_instruments = []
        
        # Fetch holdings
        stocks, mfs = self.holdings_service.fetch_holdings(mock_kite)
        
        # Verify fetch
        self.assertEqual(len(stocks), 2)
        self.assertEqual(stocks[0]["tradingsymbol"], "RELIANCE")
        
        # Add account info
        self.holdings_service.add_account_info(stocks, "TestAccount")
        
        # Verify enrichment
        self.assertEqual(stocks[0]["account"], "TestAccount")
        self.assertEqual(stocks[0]["invested"], 24000.0)
        self.assertEqual(stocks[1]["invested"], 17500.0)
        
        # Merge (single account case)
        merged_stocks, merged_mfs = self.holdings_service.merge_holdings([stocks], [mfs])
        
        self.assertEqual(len(merged_stocks), 2)
        self.assertEqual(merged_stocks[0]["tradingsymbol"], "RELIANCE")
        self.assertEqual(merged_stocks[1]["tradingsymbol"], "TCS")
    
    def test_multi_account_merge(self):
        """Test merging holdings from multiple accounts"""
        # Account 1 holdings
        account1_stocks = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "NSE",
                "quantity": 10,
                "average_price": 2400.0
            }
        ]
        self.holdings_service.add_account_info(account1_stocks, "Account1")
        
        # Account 2 holdings
        account2_stocks = [
            {
                "tradingsymbol": "TCS",
                "exchange": "NSE",
                "quantity": 5,
                "average_price": 3500.0
            }
        ]
        self.holdings_service.add_account_info(account2_stocks, "Account2")
        
        # Merge
        merged_stocks, _ = self.holdings_service.merge_holdings(
            [account1_stocks, account2_stocks],
            [[], []]
        )
        
        # Verify
        self.assertEqual(len(merged_stocks), 2)
        accounts = {h["account"] for h in merged_stocks}
        self.assertEqual(accounts, {"Account1", "Account2"})
    
    def test_state_transitions(self):
        """Test state manager transitions during workflow"""
        state_manager = StateManager()
        
        # Initial state
        self.assertEqual(state_manager.refresh_state, "updating")
        
        # Simulate refresh workflow
        state_manager.set_refresh_running()
        self.assertEqual(state_manager.get_combined_state(), "updating")
        
        state_manager.set_holdings_updated()
        self.assertIsNotNone(state_manager.holdings_last_updated)
        
        state_manager.set_refresh_idle()
        state_manager.set_ltp_idle()
        self.assertEqual(state_manager.get_combined_state(), "updated")
    
    def test_session_token_workflow(self):
        """Test session token caching workflow"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_file = f.name
        
        try:
            session_manager = SessionManager(temp_file)
            
            # Save token
            session_manager.set_token("Account1", "token123")
            session_manager.save()
            
            # Retrieve in new instance (simulates restart)
            new_session_manager = SessionManager(temp_file)
            new_session_manager.load()
            retrieved_token = new_session_manager.get_token("Account1")
            
            self.assertEqual(retrieved_token, "token123")
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_error_handling_chain(self):
        """Test error handling across services with API errors"""
        # Create mock that raises exception
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        
        # Override holdings method to raise error
        def raise_api_error():
            raise Exception("KiteConnect API Error: Network timeout")
        
        mock_kite.holdings = raise_api_error
        
        # Should raise exception
        with self.assertRaises(Exception) as context:
            self.holdings_service.fetch_holdings(mock_kite)
        
        self.assertIn("API Error", str(context.exception))
    
    def test_mf_holdings_with_nav_dates(self):
        """Test MF holdings fetch with NAV date enrichment"""
        mock_kite = MockKiteConnect(api_key="test_api_key")
        mock_kite.set_access_token("test_token")
        
        # Set up MF holdings
        mock_kite._mock_mf_holdings = [
            {
                "tradingsymbol": "INF209K01157",
                "folio": "12345678",
                "quantity": 100.523,
                "average_price": 52.45,
                "last_price": 54.20,
                "pnl": 175.90
            }
        ]
        
        # Set up MF instruments with NAV dates
        mock_kite._mock_mf_instruments = [
            {
                "tradingsymbol": "INF209K01157",
                "name": "HDFC Balanced Advantage Fund",
                "last_price": 54.20,
                "last_price_date": "2025-11-21"
            }
        ]
        
        # Fetch holdings
        stocks, mfs = self.holdings_service.fetch_holdings(mock_kite)
        
        # Verify MF holdings
        self.assertEqual(len(mfs), 1)
        self.assertEqual(mfs[0]["tradingsymbol"], "INF209K01157")
        self.assertEqual(mfs[0]["last_price_date"], "2025-11-21")
        
        # Add account info
        self.holdings_service.add_account_info(mfs, "MFAccount")
        
        # Verify invested calculation
        expected_invested = 100.523 * 52.45
        self.assertAlmostEqual(mfs[0]["invested"], expected_invested, places=2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def test_empty_holdings(self):
        """Test handling empty holdings"""
        service = HoldingsService()
        stocks, mfs = service.merge_holdings([], [])
        
        self.assertEqual(len(stocks), 0)
        self.assertEqual(len(mfs), 0)
    
    def test_zero_quantity_holdings(self):
        """Test holdings with zero quantity"""
        service = HoldingsService()
        holdings = [{"quantity": 0, "average_price": 100.0}]
        
        service.add_account_info(holdings, "Test")
        
        self.assertEqual(holdings[0]["invested"], 0.0)
    
    def test_negative_prices(self):
        """Test handling negative prices (shouldn't happen but defensively)"""
        service = HoldingsService()
        holdings = [{"quantity": 10, "average_price": -100.0}]
        
        service.add_account_info(holdings, "Test")
        
        # Should still calculate (even if negative)
        self.assertEqual(holdings[0]["invested"], -1000.0)
    
    def test_very_large_numbers(self):
        """Test handling very large portfolio values"""
        service = HoldingsService()
        holdings = [{"quantity": 1000000, "average_price": 10000.0}]
        
        service.add_account_info(holdings, "Test")
        
        self.assertEqual(holdings[0]["invested"], 10000000000.0)
    
    def test_unicode_symbols(self):
        """Test handling unicode characters in symbols"""
        service = HoldingsService()
        holdings = [
            {
                "tradingsymbol": "टेस्ट",  # Hindi characters
                "quantity": 10,
                "average_price": 100.0
            }
        ]
        
        service.add_account_info(holdings, "Test")
        
        self.assertEqual(holdings[0]["account"], "Test")


if __name__ == '__main__':
    unittest.main()
