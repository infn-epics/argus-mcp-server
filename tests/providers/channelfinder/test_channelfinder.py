import httpx
import pytest
import respx

from argus.config.settings import ChannelFinderSettings
from argus.providers.channelfinder.channelfinder import ChannelFinderProvider
from argus.providers.channelfinder.exceptions import ChannelFinderUnavailableError, ChannelFinderUnconfiguredError


def _configured() -> ChannelFinderProvider:
    return ChannelFinderProvider(ChannelFinderSettings(_env_file=None, CHANNELFINDER_BASE_URL="http://cf.test"))


async def test_unconfigured_raises_clean_error():
    provider = ChannelFinderProvider(ChannelFinderSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(ChannelFinderUnconfiguredError):
        await provider.find_channels("QF12")


@respx.mock
async def test_find_channels_parses_properties_and_tags():
    provider = _configured()
    respx.get("http://cf.test/ChannelFinder/resources/channels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "QF12:CURRENT",
                    "owner": "ops",
                    "properties": [{"name": "device", "value": "QF12"}],
                    "tags": [{"name": "magnet"}],
                }
            ],
        )
    )
    channels = await provider.find_channels(device="QF12")
    assert channels[0].name == "QF12:CURRENT"
    assert channels[0].properties == {"device": "QF12"}
    assert channels[0].tags == ["magnet"]


@respx.mock
async def test_get_channel_returns_none_on_404():
    provider = _configured()
    respx.get("http://cf.test/ChannelFinder/resources/channels/missing").mock(return_value=httpx.Response(404))
    assert await provider.get_channel("missing") is None


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.get("http://cf.test/ChannelFinder/resources/channels").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ChannelFinderUnavailableError):
        await provider.find_channels("QF12")
