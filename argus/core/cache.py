"""A small async-safe TTL cache used for ChannelFinder, Kubernetes and device metadata.

Never used for live PV values (explicitly excluded per the ARGUS caching policy).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    """Wraps ``cachetools.TTLCache`` with async-safe get-or-set semantics.

    Concurrent callers requesting the same missing key share a single in-flight
    fetch instead of each triggering their own backend call.
    """

    def __init__(self, maxsize: int = 1024, ttl: float = 60.0) -> None:
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        try:
            return self._cache[key]
        except KeyError:
            pass

        lock = await self._lock_for(key)
        async with lock:
            try:
                return self._cache[key]
            except KeyError:
                value = await factory()
                self._cache[key] = value
                return value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
