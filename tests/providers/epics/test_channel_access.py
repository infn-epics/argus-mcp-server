import aioca
import pytest

from argus.config.settings import EpicsSettings
from argus.providers.epics.channel_access import ChannelAccessProvider
from argus.providers.epics.exceptions import EpicsConnectionError, EpicsUnconfiguredError


class _FakeAugmentedFloat(float):
    pass


def _make_value(value, **attrs):
    v = _FakeAugmentedFloat(value)
    defaults = {"ok": True, "timestamp": None, "severity": 0, "status": 0}
    for key, val in {**defaults, **attrs}.items():
        setattr(v, key, val)
    return v


def _configured_provider() -> ChannelAccessProvider:
    return ChannelAccessProvider(EpicsSettings(EPICS_CA_ADDR_LIST="127.0.0.1"))


async def test_unconfigured_provider_raises_on_get():
    provider = ChannelAccessProvider(EpicsSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(EpicsUnconfiguredError):
        await provider.get("some:pv")


async def test_get_returns_pv_value(monkeypatch):
    provider = _configured_provider()

    async def fake_caget(pv_name, format, timeout):
        return _make_value(4.2, severity=0, status=0)

    monkeypatch.setattr(aioca, "caget", fake_caget)

    result = await provider.get("QF12:CURRENT")
    assert result.name == "QF12:CURRENT"
    assert float(result.value) == 4.2


async def test_get_translates_canothing_into_argus_error(monkeypatch):
    provider = _configured_provider()

    async def fake_caget(pv_name, format, timeout):
        raise aioca.CANothing(pv_name, 1)

    monkeypatch.setattr(aioca, "caget", fake_caget)

    with pytest.raises(EpicsConnectionError):
        await provider.get("QF12:CURRENT")


async def test_put_writes_value(monkeypatch):
    provider = _configured_provider()
    seen = {}

    async def fake_caput(pv_name, value, timeout):
        seen["pv_name"] = pv_name
        seen["value"] = value
        return True

    monkeypatch.setattr(aioca, "caput", fake_caput)

    result = await provider.put("QF12:CURRENT", 5.0)
    assert result.accepted is True
    assert seen == {"pv_name": "QF12:CURRENT", "value": 5.0}


async def test_get_many_marks_disconnected_pvs(monkeypatch):
    provider = _configured_provider()

    async def fake_caget(pv_names, format, timeout, throw):
        ok_value = _make_value(1.0)
        bad_value = aioca.CANothing("QF12:BAD", errorcode=200)  # non-ECA_NORMAL -> ok=False
        return [ok_value, bad_value]

    monkeypatch.setattr(aioca, "caget", fake_caget)

    results = await provider.get_many(["QF12:OK", "QF12:BAD"])
    assert results[0].status is None
    assert results[1].status == "disconnected"
