"""
Portfolio data cache and thread synchronization.
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PortfolioCache:
    """Container for all cached portfolio data."""
    stocks: List[Dict[str, Any]] = None
    mf_holdings: List[Dict[str, Any]] = None
    sips: List[Dict[str, Any]] = None
    nifty50: List[Dict[str, Any]] = None
    physical_gold: List[Dict[str, Any]] = None
    fixed_deposits: List[Dict[str, Any]] = None
    fd_summary: List[Dict[str, Any]] = None
    gold_prices: Dict[str, Dict[str, float]] = None
    gold_prices_last_fetch: Optional[datetime] = None
    market_indices: Dict[str, Any] = None
    market_indices_last_fetch: Optional[datetime] = None

    def __post_init__(self):
        self.stocks = self.stocks or []
        self.mf_holdings = self.mf_holdings or []
        self.sips = self.sips or []
        self.nifty50 = self.nifty50 or []
        self.physical_gold = self.physical_gold or []
        self.fixed_deposits = self.fixed_deposits or []
        self.fd_summary = self.fd_summary or []
        self.gold_prices = self.gold_prices or {}


# Global cache instance
cache = PortfolioCache()

# Thread synchronization events
fetch_in_progress = threading.Event()
nifty50_fetch_in_progress = threading.Event()
