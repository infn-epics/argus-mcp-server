import asyncio

from argus.core.cache import AsyncTTLCache


async def test_get_or_set_caches_value():
    cache = AsyncTTLCache(ttl=60)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return "value"

    assert await cache.get_or_set("k", factory) == "value"
    assert await cache.get_or_set("k", factory) == "value"
    assert calls == 1


async def test_get_or_set_expires_after_ttl():
    cache = AsyncTTLCache(ttl=0.05)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        return calls

    assert await cache.get_or_set("k", factory) == 1
    await asyncio.sleep(0.1)
    assert await cache.get_or_set("k", factory) == 2


async def test_get_or_set_dedupes_concurrent_calls():
    cache = AsyncTTLCache(ttl=60)
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "value"

    results = await asyncio.gather(*(cache.get_or_set("k", factory) for _ in range(5)))
    assert results == ["value"] * 5
    assert calls == 1


async def test_invalidate_removes_key():
    cache = AsyncTTLCache(ttl=60)
    await cache.get_or_set("k", lambda: _immediate("a"))
    cache.invalidate("k")
    assert await cache.get_or_set("k", lambda: _immediate("b")) == "b"


async def _immediate(value):
    return value
