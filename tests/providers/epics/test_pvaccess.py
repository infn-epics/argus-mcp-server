import asyncio

import pytest

from argus.config.settings import EpicsSettings
from argus.providers.epics.exceptions import EpicsConnectionError, EpicsTimeoutError, EpicsUnconfiguredError
from argus.providers.epics.pvaccess import PvAccessProvider


class _FakeValue:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, key):
        raise KeyError(key)


class _FakeContext:
    """Mirrors p4p's real Context.get/put signatures exactly (name, request=None,
    and put's process/wait/get) -- no timeout/throw kwargs. A provider call
    that (re)introduces those unsupported kwargs raises TypeError here just
    like it does against the real p4p Context, which is the regression this
    file guards against.
    """

    def __init__(self) -> None:
        self.get_calls: list[str] = []
        self.put_calls: list[tuple[str, object]] = []
        self.responses: dict[str, object] = {}
        self.delay = 0.0
        self.error: Exception | None = None

    async def get(self, name, request=None):
        self.get_calls.append(name)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.responses.get(name, _FakeValue(0.0))

    async def put(self, name, values, request=None, process=None, wait=None, get=True):
        self.put_calls.append((name, values))


def _configured_provider() -> tuple[PvAccessProvider, _FakeContext]:
    provider = PvAccessProvider(EpicsSettings(_env_file=None, EPICS_PVA_ADDR_LIST="127.0.0.1"))
    fake_ctx = _FakeContext()
    provider._context = fake_ctx
    return provider, fake_ctx


async def test_unconfigured_provider_raises_on_get():
    provider = PvAccessProvider(EpicsSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(EpicsUnconfiguredError):
        await provider.get("some:pv")


async def test_get_returns_pv_value():
    provider, ctx = _configured_provider()
    ctx.responses["QUATB002:CURRENT"] = _FakeValue(4.2)

    result = await provider.get("QUATB002:CURRENT")

    assert result.name == "QUATB002:CURRENT"
    assert result.value == 4.2
    assert ctx.get_calls == ["QUATB002:CURRENT"]


async def test_get_timeout_raises_epics_timeout_error():
    provider, ctx = _configured_provider()
    ctx.delay = 10.0

    with pytest.raises(EpicsTimeoutError):
        await provider.get("QUATB002:CURRENT", timeout=0.01)


async def test_get_translates_exception_to_connection_error():
    provider, ctx = _configured_provider()
    ctx.error = RuntimeError("disconnected")

    with pytest.raises(EpicsConnectionError):
        await provider.get("QUATB002:CURRENT")


async def test_put_writes_value():
    provider, ctx = _configured_provider()

    result = await provider.put("QUATB002:CURRENT", 5.0)

    assert result.accepted is True
    assert ctx.put_calls == [("QUATB002:CURRENT", 5.0)]


async def test_put_timeout_raises_epics_timeout_error():
    provider, ctx = _configured_provider()

    async def slow_put(name, values, request=None, process=None, wait=None, get=True):
        await asyncio.sleep(10.0)

    ctx.put = slow_put

    with pytest.raises(EpicsTimeoutError):
        await provider.put("QUATB002:CURRENT", 5.0, timeout=0.01)


async def test_get_many_marks_disconnected_pvs_on_individual_failure():
    provider, ctx = _configured_provider()
    ctx.responses["OK"] = _FakeValue(1.0)
    real_get = ctx.get

    async def flaky_get(name, request=None):
        if name == "BAD":
            raise RuntimeError("no such pv")
        return await real_get(name, request=request)

    ctx.get = flaky_get

    results = await provider.get_many(["OK", "BAD"])

    assert results[0].status is None
    assert results[0].value == 1.0
    assert results[1].status == "disconnected"


async def test_get_many_marks_disconnected_on_per_pv_timeout():
    provider, ctx = _configured_provider()
    ctx.responses["OK"] = _FakeValue(1.0)
    real_get = ctx.get

    async def one_slow_get(name, request=None):
        if name == "SLOW":
            await asyncio.sleep(10.0)
        return await real_get(name, request=request)

    ctx.get = one_slow_get

    results = await provider.get_many(["OK", "SLOW"], timeout=0.01)

    assert results[0].value == 1.0
    assert results[1].status == "disconnected"
