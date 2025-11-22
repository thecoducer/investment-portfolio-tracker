"""
Unit tests for constants
"""
import unittest
from constants import (
    STATE_UPDATING,
    STATE_UPDATED,
    STATE_ERROR,
    HTTP_OK,
    HTTP_ACCEPTED,
    HTTP_CONFLICT,
    EXCHANGE_NSE,
    EXCHANGE_BSE,
    EXCHANGE_SUFFIX,
    NSE_API_URL
)


class TestConstants(unittest.TestCase):
    """Test application constants"""
    
    def test_state_constants(self):
        """Test state constant values"""
        self.assertEqual(STATE_UPDATING, "updating")
        self.assertEqual(STATE_UPDATED, "updated")
        self.assertEqual(STATE_ERROR, "error")
    
    def test_http_status_constants(self):
        """Test HTTP status code constants"""
        self.assertEqual(HTTP_OK, 200)
        self.assertEqual(HTTP_ACCEPTED, 202)
        self.assertEqual(HTTP_CONFLICT, 409)
    
    def test_exchange_constants(self):
        """Test exchange constants"""
        self.assertEqual(EXCHANGE_NSE, "NSE")
        self.assertEqual(EXCHANGE_BSE, "BSE")
    
    def test_exchange_suffix_mapping(self):
        """Test exchange suffix mapping"""
        self.assertIsInstance(EXCHANGE_SUFFIX, dict)
        self.assertEqual(EXCHANGE_SUFFIX.get("NSE"), ":NSE")
        self.assertEqual(EXCHANGE_SUFFIX.get("BSE"), ":BSE")
    
    def test_nse_api_url(self):
        """Test NSE API URL is valid"""
        self.assertIsInstance(NSE_API_URL, str)
        self.assertTrue(NSE_API_URL.startswith("http"))
    
    def test_default_values(self):
        """Test default configuration values"""
        from constants import (
            DEFAULT_CALLBACK_HOST,
            DEFAULT_CALLBACK_PORT,
            DEFAULT_UI_PORT,
            DEFAULT_REQUEST_TOKEN_TIMEOUT,
            DEFAULT_LTP_FETCH_INTERVAL
        )
        
        self.assertEqual(DEFAULT_CALLBACK_HOST, "127.0.0.1")
        self.assertIsInstance(DEFAULT_CALLBACK_PORT, int)
        self.assertIsInstance(DEFAULT_UI_PORT, int)
        self.assertIsInstance(DEFAULT_REQUEST_TOKEN_TIMEOUT, int)
        self.assertIsInstance(DEFAULT_LTP_FETCH_INTERVAL, int)
        
        # Sanity checks on values
        self.assertGreater(DEFAULT_CALLBACK_PORT, 0)
        self.assertGreater(DEFAULT_UI_PORT, 0)
        self.assertGreater(DEFAULT_REQUEST_TOKEN_TIMEOUT, 0)
        self.assertGreater(DEFAULT_LTP_FETCH_INTERVAL, 0)


if __name__ == '__main__':
    unittest.main()
