"""Per-user SSE client management and targeted broadcasting.

Production considerations:
- Per-user and global client limits prevent resource exhaustion.
- Queue overflow is handled gracefully (logged, client removed).
- Thread-safe with fine-grained locking.
- Client count metrics exposed for monitoring.
"""

import threading
import time
from queue import Full, Queue
from typing import Dict, List, Optional, Set, Tuple

from .logging_config import logger

# Limits to prevent resource exhaustion in production
MAX_CLIENTS_PER_USER = 5     # max browser tabs / connections per user
MAX_TOTAL_CLIENTS = 200       # hard cap across all users
SSE_QUEUE_SIZE = 50           # per-client message buffer
SSE_RETRY_MS = 3000           # retry hint sent to clients (milliseconds)
SSE_MAX_CONNECTION_AGE = 1800 # max SSE connection lifetime in seconds (30 min)

# Sentinel value pushed into a client queue to signal it should close.
# Using a unique object ensures it can never collide with real data.
EVICT_SENTINEL = object()


class SSEClientManager:
    """Manages per-user SSE client queues. Thread-safe.

    Each client is a ``Queue`` associated with a ``google_id``.
    Limits are enforced on add to prevent unbounded growth.
    """

    def __init__(
        self,
        max_per_user: int = MAX_CLIENTS_PER_USER,
        max_total: int = MAX_TOTAL_CLIENTS,
        queue_size: int = SSE_QUEUE_SIZE,
    ):
        self._user_clients: Dict[str, List[Queue]] = {}
        self._anonymous_clients: List[Queue] = []
        self.lock = threading.Lock()
        self._max_per_user = max_per_user
        self._max_total = max_total
        self._queue_size = queue_size

    @property
    def total_client_count(self) -> int:
        """Return total number of connected SSE clients."""
        with self.lock:
            count = len(self._anonymous_clients)
            for queues in self._user_clients.values():
                count += len(queues)
            return count

    def add_client(self, client_queue: Queue, google_id: Optional[str] = None) -> bool:
        """Register a client queue. Returns False only if the global limit is hit.

        When the per-user limit is reached the *oldest* connection for that user
        is evicted (sent ``EVICT_SENTINEL``) so the new one can be accepted.
        This prevents stale/zombie connections from blocking legitimate reconnects.
        """
        with self.lock:
            # Enforce global limit
            total = len(self._anonymous_clients)
            for queues in self._user_clients.values():
                total += len(queues)
            if total >= self._max_total:
                logger.warning(
                    "SSE global client limit reached (%d). Rejecting new connection.",
                    self._max_total,
                )
                return False

            if google_id:
                user_queues = self._user_clients.setdefault(google_id, [])
                # Evict oldest connections until we are under the per-user cap
                while len(user_queues) >= self._max_per_user:
                    oldest = user_queues.pop(0)
                    logger.info(
                        "SSE evicting oldest connection for user=%s (had %d)",
                        google_id[:8], len(user_queues) + 1,
                    )
                    try:
                        oldest.put_nowait(EVICT_SENTINEL)
                    except Full:
                        pass  # queue is full — generator will clean up anyway
                user_queues.append(client_queue)
                logger.info(
                    "SSE client connected: user=%s tabs=%d total=%d users=%d",
                    google_id[:8], len(user_queues), total + 1, len(self._user_clients),
                )
            else:
                self._anonymous_clients.append(client_queue)
                logger.info("SSE anonymous client connected: total=%d", total + 1)
            return True

    def remove_client(self, client_queue: Queue, google_id: Optional[str] = None) -> None:
        with self.lock:
            if google_id and google_id in self._user_clients:
                try:
                    self._user_clients[google_id].remove(client_queue)
                except ValueError:
                    pass
                remaining_tabs = len(self._user_clients.get(google_id, []))
                if not self._user_clients.get(google_id):
                    self._user_clients.pop(google_id, None)
                    logger.info(
                        "SSE last client disconnected: user=%s total_users=%d",
                        google_id[:8], len(self._user_clients),
                    )
                else:
                    logger.debug(
                        "SSE client disconnected: user=%s remaining_tabs=%d",
                        google_id[:8], remaining_tabs,
                    )
            else:
                try:
                    self._anonymous_clients.remove(client_queue)
                except ValueError:
                    pass

    def _send_to_queues(
        self, queues: List[Queue], message: str, google_id: Optional[str] = None,
    ) -> List[Tuple[Queue, Optional[str]]]:
        """Send message to queues, return list of (queue, google_id) for failures."""
        failed: List[Tuple[Queue, Optional[str]]] = []
        for q in queues[:]:
            try:
                q.put_nowait(message)
            except Full:
                logger.warning(
                    "SSE queue full for user=%s — dropping client", google_id or "anon"
                )
                failed.append((q, google_id))
            except Exception:
                logger.exception("Failed to send SSE message to user=%s", google_id or "anon")
                failed.append((q, google_id))
        return failed

    def broadcast_to_user(self, google_id: str, message: str) -> None:
        with self.lock:
            queues = self._user_clients.get(google_id, [])
            num_targets = len(queues)
            failed = self._send_to_queues(queues, message, google_id)
        if failed:
            logger.warning(
                "SSE broadcast to user=%s: %d/%d failed",
                google_id[:8], len(failed), num_targets,
            )
        for q, gid in failed:
            self.remove_client(q, gid)

    def broadcast_all(self, message: str) -> None:
        failed: List[Tuple[Queue, Optional[str]]] = []
        with self.lock:
            for gid, queues in self._user_clients.items():
                failed.extend(self._send_to_queues(queues, message, gid))
            failed.extend(self._send_to_queues(self._anonymous_clients, message, None))
        for q, gid in failed:
            self.remove_client(q, gid)

    def connected_user_ids(self) -> Set[str]:
        with self.lock:
            return set(self._user_clients.keys())


sse_manager = SSEClientManager()
