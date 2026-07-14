from argus.core.cache import AsyncTTLCache
from argus.providers.channelfinder.models import CFChannel
from argus.services.device_service import DeviceService


class _UnconfiguredChannelFinder:
    def is_configured(self) -> bool:
        return False


class _ConfiguredChannelFinder:
    def is_configured(self) -> bool:
        return True

    async def find_channels(self, **kwargs):
        return [
            CFChannel(
                name="QF12:CURRENT",
                owner="ops",
                properties={"device": "QF12", "iocName": "ioc-qf12", "rack": "R3"},
                tags=["magnet"],
            ),
            CFChannel(
                name="QF12:STATUS",
                owner="ops",
                properties={"device": "QF12", "iocName": "ioc-qf12"},
                tags=["magnet"],
            ),
        ]


async def test_resolve_device_falls_back_to_bare_pv_when_unconfigured():
    service = DeviceService(channelfinder=_UnconfiguredChannelFinder(), cache=AsyncTTLCache(ttl=60))
    device = await service.resolve_device("QF12:CURRENT")
    assert device.name == "QF12:CURRENT"
    assert device.pv_names == ["QF12:CURRENT"]
    assert device.ioc_name is None


async def test_resolve_device_merges_channel_metadata():
    service = DeviceService(channelfinder=_ConfiguredChannelFinder(), cache=AsyncTTLCache(ttl=60))
    device = await service.resolve_device("QF12")
    assert set(device.pv_names) == {"QF12:CURRENT", "QF12:STATUS"}
    assert device.ioc_name == "ioc-qf12"
    assert device.rack == "R3"
    assert device.owner == "ops"
    assert device.tags == ["magnet"]


async def test_resolve_device_is_cached():
    channelfinder = _ConfiguredChannelFinder()
    calls = 0
    original = channelfinder.find_channels

    async def counting_find_channels(**kwargs):
        nonlocal calls
        calls += 1
        return await original(**kwargs)

    channelfinder.find_channels = counting_find_channels
    service = DeviceService(channelfinder=channelfinder, cache=AsyncTTLCache(ttl=60))

    await service.resolve_device("QF12")
    await service.resolve_device("QF12")
    assert calls == 1
