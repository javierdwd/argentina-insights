"""In-memory TTL cache for upstream ArgentinaDatos payloads.

Deliberately not Redis: the full set of lists we care about (actas for both
chambers, both rosters, the finance series) is on the order of a few MB of
JSON in a single process.  Redis would add ops and a dependency without
buying anything until we run multiple agent instances.

Cached values are the FULL upstream list for a path.  All filtering,
projection and capping happens downstream on the cached payload, so the
second "give me acta 5995" request after a list fetch costs no HTTP call.

Invalidation is TTL-only; ``refresh=true`` on a proxy call forces a re-fetch.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    payload: Any
    expires_at: float


class TTLCache:
    """Async-safe TTL cache with per-key fetch coalescing.

    Two tool calls in the same turn often hit the same upstream list (e.g.
    "actas" then "acta by id").  The per-key lock makes the second one wait
    for the in-flight fetch instead of firing a duplicate request.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def peek(self, key: str) -> Any | None:
        """Return a live cached value, or None when missing/expired."""
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= time.monotonic():
            return None
        return entry.payload

    async def get_or_fetch(
        self,
        key: str,
        ttl: float,
        fetch: Callable[[], Awaitable[Any]],
        *,
        refresh: bool = False,
    ) -> Any:
        """Return the cached payload for *key*, fetching it when needed.

        Args:
            key:     Cache key (the upstream path).
            ttl:     Seconds the freshly fetched value stays valid.
            fetch:   Coroutine factory performing the upstream request.
            refresh: Skip the cached value and re-fetch.
        """
        if not refresh:
            cached = self.peek(key)
            if cached is not None:
                return cached

        async with self._lock_for(key):
            # Another coroutine may have populated it while we waited.
            if not refresh:
                cached = self.peek(key)
                if cached is not None:
                    return cached

            payload = await fetch()
            self._entries[key] = _Entry(
                payload=payload,
                expires_at=time.monotonic() + ttl,
            )
            return payload

    def put(self, key: str, payload: Any, ttl: float) -> None:
        """Store *payload* under *key* for *ttl* seconds."""
        self._entries[key] = _Entry(
            payload=payload,
            expires_at=time.monotonic() + ttl,
        )

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()


#: Process-wide cache shared by every proxy call.
cache = TTLCache()
