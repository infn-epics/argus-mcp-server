import asyncio

from argus.core.errors import ProviderUnavailableError, ProviderUnconfiguredError
from argus.core.models import gather_with_timeout


async def _ok():
    return "value"


async def _slow():
    await asyncio.sleep(1)
    return "too late"


async def _raises_unconfigured():
    raise ProviderUnconfiguredError("not configured")


async def _raises_unavailable():
    raise ProviderUnavailableError("down")


async def _raises_generic():
    raise RuntimeError("boom")


async def test_gather_with_timeout_all_ok():
    results = await gather_with_timeout({"a": _ok(), "b": _ok()}, timeout=1)
    assert results["a"].status == "ok"
    assert results["a"].data == "value"
    assert results["b"].status == "ok"


async def test_gather_with_timeout_never_raises_on_slow_provider():
    results = await gather_with_timeout({"slow": _slow(), "fast": _ok()}, timeout=0.05)
    assert results["slow"].status == "timeout"
    assert results["fast"].status == "ok"


async def test_gather_with_timeout_degrades_on_provider_errors():
    results = await gather_with_timeout(
        {
            "unconfigured": _raises_unconfigured(),
            "unavailable": _raises_unavailable(),
            "broken": _raises_generic(),
            "ok": _ok(),
        },
        timeout=1,
    )
    assert results["unconfigured"].status == "unconfigured"
    assert results["unavailable"].status == "unavailable"
    assert results["broken"].status == "error"
    assert results["ok"].status == "ok"
