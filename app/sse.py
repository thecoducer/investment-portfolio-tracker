"""
Server-Sent Events (SSE) client management.
"""

import threading
from queue import Queue
from typing import List

from .logging_config import logger


class SSEClientManager:
    """Manages Server-Sent Events client connections and message broadcasting."""

    def __init__(self):
        self.clients: List[Queue] = []
        self.lock = threading.Lock()

    def add_client(self, client_queue: Queue) -> None:
        """Add a new SSE client connection."""
        with self.lock:
            self.clients.append(client_queue)

    def remove_client(self, client_queue: Queue) -> None:
        """Remove an SSE client connection."""
        with self.lock:
            try:
                self.clients.remove(client_queue)
            except ValueError:
                pass

    def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected SSE clients."""
        failed_clients = []
        with self.lock:
            for client_queue in self.clients[:]:
                try:
                    client_queue.put_nowait(message)
                except Exception:
                    logger.exception("Failed to send SSE message to client, removing")
                    failed_clients.append(client_queue)
        for client_queue in failed_clients:
            self.remove_client(client_queue)


# Module-level instance
sse_manager = SSEClientManager()
