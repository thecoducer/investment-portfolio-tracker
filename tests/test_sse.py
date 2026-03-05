"""
Unit tests for sse.py (per-user SSE client manager) — production hardening.
"""
import unittest
from queue import Full, Queue

from app.sse import EVICT_SENTINEL, SSEClientManager, sse_manager


class TestSSEClientManager(unittest.TestCase):
    """Test SSEClientManager with per-user isolation."""

    def test_add_and_remove_user_client(self):
        manager = SSEClientManager()
        q = Queue()
        self.assertTrue(manager.add_client(q, google_id="user1"))
        self.assertIn("user1", manager.connected_user_ids())
        manager.remove_client(q, google_id="user1")
        self.assertNotIn("user1", manager.connected_user_ids())

    def test_add_anonymous_client(self):
        manager = SSEClientManager()
        q = Queue()
        self.assertTrue(manager.add_client(q))
        self.assertEqual(len(manager._anonymous_clients), 1)
        manager.remove_client(q)
        self.assertEqual(len(manager._anonymous_clients), 0)

    def test_remove_nonexistent_client(self):
        manager = SSEClientManager()
        q = Queue()
        # Should not raise
        manager.remove_client(q, google_id="nonexistent")
        manager.remove_client(q)

    def test_broadcast_to_user(self):
        """Messages sent via broadcast_to_user go only to that user."""
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user2")

        manager.broadcast_to_user("user1", "hello_user1")

        self.assertEqual(q1.get_nowait(), "hello_user1")
        self.assertTrue(q2.empty())

    def test_broadcast_all(self):
        """broadcast_all sends to all user + anonymous clients."""
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        q_anon = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user2")
        manager.add_client(q_anon)

        manager.broadcast_all("global_msg")

        self.assertEqual(q1.get_nowait(), "global_msg")
        self.assertEqual(q2.get_nowait(), "global_msg")
        self.assertEqual(q_anon.get_nowait(), "global_msg")

    def test_connected_user_ids(self):
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user2")

        ids = manager.connected_user_ids()
        self.assertEqual(ids, {"user1", "user2"})

    def test_connected_user_ids_empty(self):
        manager = SSEClientManager()
        self.assertEqual(manager.connected_user_ids(), set())

    def test_multiple_clients_per_user(self):
        """One user can have multiple browser tabs / connections."""
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user1")

        manager.broadcast_to_user("user1", "msg")

        self.assertEqual(q1.get_nowait(), "msg")
        self.assertEqual(q2.get_nowait(), "msg")

    def test_remove_one_of_multiple_clients(self):
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user1")

        manager.remove_client(q1, google_id="user1")

        # user1 should still be connected (q2 remains)
        self.assertIn("user1", manager.connected_user_ids())

        manager.remove_client(q2, google_id="user1")
        # Now fully disconnected
        self.assertNotIn("user1", manager.connected_user_ids())

    def test_user_isolation_no_cross_delivery(self):
        """Ensure user1 messages never reach user2."""
        manager = SSEClientManager()
        q1 = Queue()
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user2")

        manager.broadcast_to_user("user1", "secret")

        self.assertEqual(q1.get_nowait(), "secret")
        self.assertTrue(q2.empty())

    def test_global_instance_exists(self):
        self.assertIsInstance(sse_manager, SSEClientManager)

    # ------- Production hardening tests -------

    def test_per_user_client_limit(self):
        """Enforce max_per_user limit via eviction of oldest connection."""
        manager = SSEClientManager(max_per_user=2, max_total=100)
        q1, q2, q3 = Queue(), Queue(), Queue()
        self.assertTrue(manager.add_client(q1, google_id="user1"))
        self.assertTrue(manager.add_client(q2, google_id="user1"))
        # Third connection should evict q1 (oldest) and still succeed
        self.assertTrue(manager.add_client(q3, google_id="user1"))
        self.assertEqual(manager.total_client_count, 2)
        # q1 should have received the eviction sentinel
        self.assertIs(q1.get_nowait(), EVICT_SENTINEL)

    def test_global_client_limit(self):
        """Enforce max_total global limit across all users."""
        manager = SSEClientManager(max_per_user=10, max_total=3)
        q1, q2, q3, q4 = Queue(), Queue(), Queue(), Queue()
        self.assertTrue(manager.add_client(q1, google_id="user1"))
        self.assertTrue(manager.add_client(q2, google_id="user2"))
        self.assertTrue(manager.add_client(q3))  # anonymous
        # Fourth connection rejected
        self.assertFalse(manager.add_client(q4, google_id="user3"))
        self.assertEqual(manager.total_client_count, 3)

    def test_add_client_returns_bool(self):
        """add_client returns True on success; per-user overflow evicts oldest."""
        manager = SSEClientManager(max_per_user=1, max_total=10)
        q1, q2 = Queue(), Queue()
        result1 = manager.add_client(q1, google_id="user1")
        result2 = manager.add_client(q2, google_id="user1")
        self.assertIsInstance(result1, bool)
        self.assertTrue(result1)
        # Per-user overflow now evicts oldest instead of rejecting
        self.assertTrue(result2)
        # q1 was evicted
        self.assertIs(q1.get_nowait(), EVICT_SENTINEL)

    def test_queue_full_removes_client(self):
        """When queue is full, broadcast should remove the overflowing client."""
        manager = SSEClientManager(max_per_user=10, max_total=100, queue_size=2)
        q = Queue(maxsize=2)
        manager.add_client(q, google_id="user1")

        # Fill queue to capacity
        manager.broadcast_to_user("user1", "msg1")
        manager.broadcast_to_user("user1", "msg2")
        # This should overflow and trigger removal
        manager.broadcast_to_user("user1", "msg3")

        # Client should have been removed
        self.assertNotIn("user1", manager.connected_user_ids())

    def test_total_client_count(self):
        """total_client_count tracks all connections."""
        manager = SSEClientManager()
        self.assertEqual(manager.total_client_count, 0)
        q1, q2, q3 = Queue(), Queue(), Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user2")
        manager.add_client(q3)
        self.assertEqual(manager.total_client_count, 3)
        manager.remove_client(q1, google_id="user1")
        self.assertEqual(manager.total_client_count, 2)

    def test_broadcast_to_user_nonexistent(self):
        """Broadcasting to a user with no clients should not raise."""
        manager = SSEClientManager()
        manager.broadcast_to_user("ghost", "hello")  # no-op, no exception

    def test_after_limit_removal_allows_new_client(self):
        """After removing a client, new ones can connect up to the limit."""
        manager = SSEClientManager(max_per_user=1, max_total=10)
        q1, q2 = Queue(), Queue()
        self.assertTrue(manager.add_client(q1, google_id="user1"))
        manager.remove_client(q1, google_id="user1")
        # Now slot is free
        self.assertTrue(manager.add_client(q2, google_id="user1"))

    def test_eviction_sends_sentinel_to_oldest(self):
        """When per-user limit is hit, oldest queue gets EVICT_SENTINEL."""
        manager = SSEClientManager(max_per_user=2, max_total=100)
        q1, q2, q3, q4 = Queue(), Queue(), Queue(), Queue()
        manager.add_client(q1, google_id="user1")
        manager.add_client(q2, google_id="user1")
        # Exceed limit — q1 evicted
        manager.add_client(q3, google_id="user1")
        self.assertIs(q1.get_nowait(), EVICT_SENTINEL)
        self.assertTrue(q2.empty())  # q2 not evicted
        # Exceed again — q2 evicted
        manager.add_client(q4, google_id="user1")
        self.assertIs(q2.get_nowait(), EVICT_SENTINEL)
        self.assertEqual(manager.total_client_count, 2)

    def test_eviction_on_full_queue(self):
        """Eviction works even when the oldest queue is full."""
        manager = SSEClientManager(max_per_user=1, max_total=100, queue_size=1)
        q1 = Queue(maxsize=1)
        q1.put("existing_msg")  # fill it
        q2 = Queue()
        manager.add_client(q1, google_id="user1")
        # q1 is full, but eviction should not raise
        manager.add_client(q2, google_id="user1")
        self.assertEqual(manager.total_client_count, 1)

    def test_remove_user_client_queue_not_in_list(self):
        """remove_client when google_id has clients but the given queue is not one of them."""
        manager = SSEClientManager()
        q_real = Queue()
        q_stranger = Queue()
        manager.add_client(q_real, google_id="user1")
        # q_stranger was never added — should trigger ValueError path (caught)
        manager.remove_client(q_stranger, google_id="user1")
        # user1 should still be connected (q_real remains)
        self.assertIn("user1", manager.connected_user_ids())

    def test_send_to_queues_generic_exception(self):
        """_send_to_queues handles generic Exception (not Full) on put_nowait."""
        manager = SSEClientManager()
        bad_q = Queue()
        bad_q.put_nowait = lambda msg: (_ for _ in ()).throw(RuntimeError("broken"))
        manager.add_client(bad_q, google_id="user1")
        # broadcast_to_user calls _send_to_queues internally
        manager.broadcast_to_user("user1", "test_msg")
        # Bad client should have been removed
        self.assertNotIn("user1", manager.connected_user_ids())

    def test_broadcast_all_anonymous_failure(self):
        """broadcast_all removes anonymous clients whose queues overflow."""
        manager = SSEClientManager(max_per_user=10, max_total=100, queue_size=1)
        q_anon = Queue(maxsize=1)
        q_anon.put("fill")  # fill it
        manager.add_client(q_anon)
        # broadcast_all should try sending to anonymous client, fail, and remove it
        manager.broadcast_all("msg")
        self.assertEqual(len(manager._anonymous_clients), 0)


if __name__ == '__main__':
    unittest.main()
