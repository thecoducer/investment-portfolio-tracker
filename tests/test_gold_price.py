"""
Tests for gold price fetching service.
"""

import unittest
from unittest.mock import patch, Mock
from api.ibja_gold_price import GoldPriceService, get_gold_price_service


class TestGoldPriceService(unittest.TestCase):
    """Test cases for GoldPriceService"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = GoldPriceService()
    
    @patch('api.gold_price.requests.get')
    def test_fetch_gold_prices_success(self, mock_get):
        """Test successful fetching of gold prices."""
        # Mock HTML response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'''
        <html>
            <table>
                <tr><th>Purity</th><th>AM</th><th>PM</th></tr>
                <tr><td>Gold 999</td><td>128550</td><td>128214</td></tr>
                <tr><td>Gold 995</td><td>128035</td><td>127701</td></tr>
                <tr><td>Gold 916</td><td>117752</td><td>117444</td></tr>
                <tr><td>Gold 750</td><td>96413</td><td>96161</td></tr>
                <tr><td>Gold 585</td><td>75202</td><td>75005</td></tr>
            </table>
        </html>
        '''
        mock_get.return_value = mock_response
        
        prices = self.service.fetch_gold_prices()
        
        self.assertIsNotNone(prices)
        self.assertIn('999', prices)
        self.assertIn('916', prices)
        self.assertEqual(prices['999']['am'], 128550.0)
        self.assertEqual(prices['999']['pm'], 128214.0)
        self.assertEqual(prices['916']['am'], 117752.0)
        self.assertEqual(prices['916']['pm'], 117444.0)
    
    @patch('api.gold_price.requests.get')
    def test_fetch_gold_prices_no_tables(self, mock_get):
        """Test handling of page with no tables."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><body>No tables here</body></html>'
        mock_get.return_value = mock_response
        
        prices = self.service.fetch_gold_prices()
        
        self.assertIsNone(prices)
    
    @patch('api.gold_price.requests.get')
    def test_fetch_gold_prices_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = Exception("Network error")
        
        prices = self.service.fetch_gold_prices()
        
        self.assertIsNone(prices)
    
    @patch('api.gold_price.requests.get')
    def test_fetch_gold_prices_invalid_data(self, mock_get):
        """Test handling of invalid price data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'''
        <html>
            <table>
                <tr><th>Purity</th><th>AM</th><th>PM</th></tr>
                <tr><td>Gold 999</td><td>invalid</td><td>not_a_number</td></tr>
            </table>
        </html>
        '''
        mock_get.return_value = mock_response
        
        prices = self.service.fetch_gold_prices()
        
        # Should return None as no valid prices were found
        self.assertIsNone(prices)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_24k_price_pm(self, mock_fetch):
        """Test getting 24K PM price."""
        mock_fetch.return_value = {
            '999': {'am': 128550.0, 'pm': 128214.0},
            '916': {'am': 117752.0, 'pm': 117444.0}
        }
        
        price = self.service.get_24k_price('pm')
        
        self.assertEqual(price, 128214.0)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_24k_price_am(self, mock_fetch):
        """Test getting 24K AM price."""
        mock_fetch.return_value = {
            '999': {'am': 128550.0, 'pm': 128214.0}
        }
        
        price = self.service.get_24k_price('am')
        
        self.assertEqual(price, 128550.0)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_24k_price_default_pm(self, mock_fetch):
        """Test that PM is default for 24K price."""
        mock_fetch.return_value = {
            '999': {'am': 128550.0, 'pm': 128214.0}
        }
        
        price = self.service.get_24k_price()
        
        self.assertEqual(price, 128214.0)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_24k_price_not_available(self, mock_fetch):
        """Test handling when 24K price is not available."""
        mock_fetch.return_value = None
        
        price = self.service.get_24k_price()
        
        self.assertIsNone(price)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_22k_price_pm(self, mock_fetch):
        """Test getting 22K PM price."""
        mock_fetch.return_value = {
            '999': {'am': 128550.0, 'pm': 128214.0},
            '916': {'am': 117752.0, 'pm': 117444.0}
        }
        
        price = self.service.get_22k_price('pm')
        
        self.assertEqual(price, 117444.0)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_22k_price_am(self, mock_fetch):
        """Test getting 22K AM price."""
        mock_fetch.return_value = {
            '916': {'am': 117752.0, 'pm': 117444.0}
        }
        
        price = self.service.get_22k_price('am')
        
        self.assertEqual(price, 117752.0)
    
    @patch.object(GoldPriceService, 'fetch_gold_prices')
    def test_get_22k_price_invalid_time(self, mock_fetch):
        """Test that invalid time_of_day defaults to PM."""
        mock_fetch.return_value = {
            '916': {'am': 117752.0, 'pm': 117444.0}
        }
        
        price = self.service.get_22k_price('invalid')
        
        self.assertEqual(price, 117444.0)
    
    def test_singleton_instance(self):
        """Test that get_gold_price_service returns singleton."""
        service1 = get_gold_price_service()
        service2 = get_gold_price_service()
        
        self.assertIs(service1, service2)


if __name__ == '__main__':
    unittest.main()
