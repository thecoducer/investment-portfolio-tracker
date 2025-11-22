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
    HTTP_CONFLICT
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
    
    def test_default_values(self):
        """Test default configuration values"""
        from constants import (
            DEFAULT_CALLBACK_HOST,
            DEFAULT_CALLBACK_PORT,
            DEFAULT_UI_PORT,
            DEFAULT_REQUEST_TOKEN_TIMEOUT
        )
        
        self.assertEqual(DEFAULT_CALLBACK_HOST, "127.0.0.1")
        self.assertIsInstance(DEFAULT_CALLBACK_PORT, int)
        self.assertIsInstance(DEFAULT_UI_PORT, int)
        self.assertIsInstance(DEFAULT_REQUEST_TOKEN_TIMEOUT, int)
        
        # Sanity checks on values
        self.assertGreater(DEFAULT_CALLBACK_PORT, 0)
        self.assertGreater(DEFAULT_UI_PORT, 0)
        self.assertGreater(DEFAULT_REQUEST_TOKEN_TIMEOUT, 0)


if __name__ == '__main__':
    unittest.main()
