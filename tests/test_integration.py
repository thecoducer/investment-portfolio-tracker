"""
Integration tests for the portfolio tracker
"""
import unittest
import json
import tempfile
import os
from unittest.mock import patch, Mock

from api.holdings import HoldingsService
from api.ltp import LTPService
from utils import SessionManager, StateManager


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.holdings_service = HoldingsService()
        self.ltp_service = LTPService()
    
    def test_complete_holdings_flow(self):
        """Test complete flow: fetch, enrich, merge"""
        # Mock KiteConnect
        mock_kite = Mock()
        mock_kite.holdings.return_value = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "NSE",
                "quantity": 10,
                "average_price": 2400.0,
                "last_price": 2500.0
            }
        ]
        mock_kite.mf_holdings.return_value = []
        mock_kite.mf_instruments.return_value = []
        
        # Fetch holdings
        stocks, mfs = self.holdings_service.fetch_holdings(mock_kite)
        
        # Add account info
        self.holdings_service.add_account_info(stocks, "TestAccount")
        
        # Verify enrichment
        self.assertEqual(stocks[0]["account"], "TestAccount")
        self.assertEqual(stocks[0]["invested"], 24000.0)
        
        # Merge (single account case)
        merged_stocks, merged_mfs = self.holdings_service.merge_holdings([stocks], [mfs])
        
        self.assertEqual(len(merged_stocks), 1)
        self.assertEqual(merged_stocks[0]["tradingsymbol"], "RELIANCE")
    
    @patch('api.ltp.requests.get')
    def test_ltp_update_flow(self, mock_get):
        """Test LTP update flow"""
        # Mock successful LTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "RELIANCE:NSE": {"last_price": 2550.0}
        }
        mock_get.return_value = mock_response
        
        # Create holdings
        holdings = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "NSE",
                "last_price": 2500.0
            }
        ]
        
        # Fetch and update LTP
        ltp_data = self.ltp_service.fetch_ltps(holdings)
        self.ltp_service.update_holdings_with_ltp(holdings, ltp_data)
        
        # Verify update
        self.assertEqual(holdings[0]["last_price"], 2550.0)
    
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
        self.assertEqual(state_manager.state, "updating")
        
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
            session_manager.save_token("Account1", "token123")
            
            # Retrieve in new instance (simulates restart)
            new_session_manager = SessionManager(temp_file)
            retrieved_token = new_session_manager.get_token("Account1")
            
            self.assertEqual(retrieved_token, "token123")
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_error_handling_chain(self):
        """Test error handling across services"""
        mock_kite = Mock()
        mock_kite.holdings.side_effect = Exception("API Error")
        
        # Should not crash, returns empty lists
        with self.assertRaises(Exception):
            self.holdings_service.fetch_holdings(mock_kite)


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
    
    def test_missing_exchange_field(self):
        """Test holdings without exchange field"""
        ltp_service = LTPService()
        holdings = [{"tradingsymbol": "RELIANCE"}]  # No exchange
        
        symbols = ltp_service._prepare_symbols(holdings)
        
        # Should handle gracefully
        self.assertIsInstance(symbols, list)
    
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
