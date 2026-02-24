"""
Unit tests for sse.py (SSE client manager).
"""
import unittest
from queue import Queue

from app.sse import SSEClientManager, sse_manager


class TestSSEClientManager(unittest.TestCase):
    """Test SSEClientManager."""

    def test_add_and_remove_client(self):
        manager = SSEClientManager()
        q = Queue()
        manager.add_client(q)
        self.assertIn(q, manager.clients)
        manager.remove_client(q)
        self.assertNotIn(q, manager.clients)

    def test_remove_nonexistent_client(self):
        manager = SSEClientManager()
        q = Queue()
        # Should not raise
        manager.remove_client(q)

    def test_broadcast_sends_to_all(self):
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1)
        manager.add_client(q2)

        manager.broadcast("hello")

        self.assertEqual(q1.get_nowait(), "hello")
        self.assertEqual(q2.get_nowait(), "hello")

    def test_global_instance_exists(self):
        self.assertIsInstance(sse_manager, SSEClientManager)


if __name__ == '__main__':
    unittest.main()
