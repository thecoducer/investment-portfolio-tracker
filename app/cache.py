"""Per-user portfolio cache, global market cache, and Google Sheets TTL cache."""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UserPortfolioData:
    stocks: list[dict[str, Any]] = field(default_factory=list)
    mf_holdings: list[dict[str, Any]] = field(default_factory=list)
    sips: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MarketCache:
    nifty50: list[dict[str, Any]] = field(default_factory=list)
    gold_prices: dict[str, dict[str, float]] = field(default_factory=dict)
    gold_prices_last_fetch: datetime | None = None
    market_indices: dict[str, Any] = field(default_factory=dict)
    market_indices_last_fetch: datetime | None = None


class PortfolioCacheManager:
    """Thread-safe per-user portfolio cache with fetch-in-progress tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._user_data: dict[str, UserPortfolioData] = {}
        self._fetch_events: dict[str, threading.Event] = {}

    def get(self, google_id: str) -> UserPortfolioData:
        """Return the cached portfolio for *google_id*, creating an empty one if absent."""
        with self._lock:
            return self._user_data.setdefault(google_id, UserPortfolioData())

    def set(self, google_id: str, *, stocks: list = None, mf_holdings: list = None, sips: list = None) -> None:
        """Update one or more portfolio data fields for *google_id*."""
        with self._lock:
            data = self._user_data.setdefault(google_id, UserPortfolioData())
        if stocks is not None:
            data.stocks = stocks
        if mf_holdings is not None:
            data.mf_holdings = mf_holdings
        if sips is not None:
            data.sips = sips

    def _get_event(self, google_id: str) -> threading.Event:
        """Return the fetch-in-progress event for *google_id*, creating one if absent."""
        with self._lock:
            return self._fetch_events.setdefault(google_id, threading.Event())

    def is_fetch_in_progress(self, google_id: str) -> bool:
        """Return True if a background portfolio fetch is running for this user."""
        return self._get_event(google_id).is_set()

    def set_fetch_in_progress(self, google_id: str) -> None:
        """Mark a background portfolio fetch as running."""
        self._get_event(google_id).set()

    def clear_fetch_in_progress(self, google_id: str) -> None:
        """Mark a background portfolio fetch as finished."""
        self._get_event(google_id).clear()

    def clear(self, google_id: str) -> None:
        """Remove all cached portfolio data for *google_id*."""
        with self._lock:
            self._user_data.pop(google_id, None)

    def active_user_ids(self) -> list[str]:
        """Return google_ids of all users with cached portfolio data."""
        with self._lock:
            return list(self._user_data.keys())


market_cache = MarketCache()
portfolio_cache = PortfolioCacheManager()
nifty50_fetch_in_progress = threading.Event()


_SHEETS_CACHE_TTL = 300  # seconds


@dataclass
class _UserCacheEntry:
    physical_gold: list[dict[str, Any]] = field(default_factory=list)
    fixed_deposits: list[dict[str, Any]] = field(default_factory=list)
    provident_fund: list[dict[str, Any]] = field(default_factory=list)
    stocks: list[dict[str, Any]] = field(default_factory=list)
    etfs: list[dict[str, Any]] = field(default_factory=list)
    mutual_funds: list[dict[str, Any]] = field(default_factory=list)
    sips: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0
    # Track which sheet types have actually been fetched vs just default-empty
    _fetched_sheets: set = field(default_factory=set)


class UserSheetsCache:
    """TTL-based per-user cache for Google Sheets data. Thread-safe."""

    def __init__(self, ttl: int = _SHEETS_CACHE_TTL):
        self._ttl = ttl
        self._store: dict[str, _UserCacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, google_id: str) -> _UserCacheEntry | None:
        """Return the cache entry for *google_id* if present and not expired."""
        with self._lock:
            entry = self._store.get(google_id)
            if entry and (time.monotonic() - entry.timestamp) < self._ttl:
                return entry
            return None

    def put(
        self, google_id: str, *, physical_gold: list = None, fixed_deposits: list = None, provident_fund: list = None
    ) -> None:
        """Cache one or more sheet data types for *google_id*, refreshing the TTL."""
        with self._lock:
            now = time.monotonic()
            entry = self._store.setdefault(google_id, _UserCacheEntry(timestamp=now))
            if physical_gold is not None:
                entry.physical_gold = physical_gold
                entry.timestamp = now
            if fixed_deposits is not None:
                entry.fixed_deposits = fixed_deposits
                entry.timestamp = now
            if provident_fund is not None:
                entry.provident_fund = provident_fund
                entry.timestamp = now

    # ── Sheet-entry helpers (stocks / etfs / mutual_funds / sips) ──

    _SHEET_ATTR = {
        "stocks": "stocks",
        "etfs": "etfs",
        "mutual_funds": "mutual_funds",
        "sips": "sips",
    }

    def get_manual(self, google_id: str, sheet_type: str) -> list | None:
        """Return cached entries for *sheet_type*, or None on miss."""
        attr = self._SHEET_ATTR.get(sheet_type)
        if not attr:
            return None
        with self._lock:
            entry = self._store.get(google_id)
            if entry and (time.monotonic() - entry.timestamp) < self._ttl:
                if sheet_type in entry._fetched_sheets:
                    return getattr(entry, attr)
            return None

    def put_manual(self, google_id: str, sheet_type: str, rows: list) -> None:
        """Cache entries for *sheet_type*."""
        attr = self._SHEET_ATTR.get(sheet_type)
        if not attr:
            return
        with self._lock:
            now = time.monotonic()
            entry = self._store.setdefault(google_id, _UserCacheEntry(timestamp=now))
            setattr(entry, attr, rows)
            entry._fetched_sheets.add(sheet_type)
            entry.timestamp = now

    # ── Batch helpers ──

    _ALL_MANUAL_TYPES = frozenset(_SHEET_ATTR)

    def is_fully_cached(self, google_id: str) -> bool:
        """Return True when gold, FDs, and all 4 manual sheet types are cached."""
        with self._lock:
            entry = self._store.get(google_id)
            if not entry or (time.monotonic() - entry.timestamp) >= self._ttl:
                return False
            return self._ALL_MANUAL_TYPES.issubset(entry._fetched_sheets)

    def put_all(
        self,
        google_id: str,
        *,
        physical_gold: list = None,
        fixed_deposits: list = None,
        provident_fund: list = None,
        manual: dict[str, list] = None,
    ) -> None:
        """Cache gold, FDs, PF, and all manual sheet types in one call."""
        with self._lock:
            now = time.monotonic()
            entry = self._store.setdefault(google_id, _UserCacheEntry(timestamp=now))
            if physical_gold is not None:
                entry.physical_gold = physical_gold
            if fixed_deposits is not None:
                entry.fixed_deposits = fixed_deposits
            if provident_fund is not None:
                entry.provident_fund = provident_fund
            if manual:
                for sheet_type, rows in manual.items():
                    attr = self._SHEET_ATTR.get(sheet_type)
                    if attr:
                        setattr(entry, attr, rows)
                        entry._fetched_sheets.add(sheet_type)
            entry.timestamp = now

    def invalidate(self, google_id: str) -> None:
        """Remove all cached sheet data for *google_id*."""
        with self._lock:
            self._store.pop(google_id, None)


user_sheets_cache = UserSheetsCache()


class ManualLTPCache:
    """Thread-safe cache for manually-added stock/ETF last traded prices.

    Stores NSE quote data (ltp, change, pChange) keyed by symbol.
    No TTL — data persists until explicitly invalidated or overwritten.

    Negative lookups (unresolved symbols) use a 5-minute TTL to allow
    periodic retries for temporarily unavailable symbols.
    """

    _NEGATIVE_TTL = 300  # 5 minutes

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._negative: dict[str, float] = {}
        self._lock = threading.Lock()
        self._cancel = threading.Event()

    # -- Read --

    def get(self, symbol: str) -> dict[str, Any] | None:
        """Return cached quote data for *symbol*, or None on miss."""
        with self._lock:
            return self._data.get(symbol)

    def is_negative(self, symbol: str) -> bool:
        """Return True if *symbol* was recently recorded as unresolvable."""
        with self._lock:
            ts = self._negative.get(symbol)
            if ts is None:
                return False
            return (time.monotonic() - ts) < self._NEGATIVE_TTL

    # -- Write --

    def put(self, symbol: str, data: dict[str, Any]) -> None:
        """Cache quote data for *symbol* and remove any negative entry."""
        with self._lock:
            self._data[symbol] = data
            self._negative.pop(symbol, None)

    def put_batch(self, data: dict[str, dict[str, Any]]) -> None:
        """Cache quote data for multiple symbols at once."""
        with self._lock:
            for symbol, quote in data.items():
                self._data[symbol] = quote
                self._negative.pop(symbol, None)

    def put_negative_batch(self, symbols: list) -> None:
        """Record symbols as unresolvable (negative lookup) with a 5-minute TTL."""
        with self._lock:
            now = time.monotonic()
            for sym in symbols:
                self._negative[sym] = now

    # -- Control --

    @property
    def cancel_flag(self) -> threading.Event:
        """Event checked by background fetch threads to abort early."""
        return self._cancel

    def invalidate(self) -> None:
        """Clear all data and cancel in-flight background fetches."""
        with self._lock:
            self._data.clear()
            self._negative.clear()
        self._cancel.set()
        self._cancel = threading.Event()


manual_ltp_cache = ManualLTPCache()
