"""
Unit tests for server.py (application entry point).
"""
import threading
import time
import unittest
from unittest.mock import Mock

from app.server import start_server


class TestStartServer(unittest.TestCase):
    """Test server management functions."""

    def test_start_server_creates_daemon_thread(self):
        """Test start_server creates daemon thread and starts Flask app."""
        mock_app = Mock()
        mock_app.run = Mock()

        thread = start_server(mock_app, '127.0.0.1', 8000)

        self.assertIsInstance(thread, threading.Thread)
        self.assertTrue(thread.daemon)

        # Give thread time to start
        time.sleep(0.6)

        mock_app.run.assert_called_once_with(
            host='127.0.0.1',
            port=8000,
            debug=False,
            use_reloader=False,
        )


if __name__ == '__main__':
    unittest.main()
