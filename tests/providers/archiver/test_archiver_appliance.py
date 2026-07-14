from datetime import datetime, timedelta

import httpx
import pytest
import respx

from argus.config.settings import ArchiverSettings
from argus.providers.archiver.archiver_appliance import ArchiverApplianceProvider
from argus.providers.archiver.exceptions import ArchiverQueryError, ArchiverUnavailableError, ArchiverUnconfiguredError


def _configured() -> ArchiverApplianceProvider:
    return ArchiverApplianceProvider(ArchiverSettings(_env_file=None, ARCHIVER_BASE_URL="http://archiver.test"))


async def test_unconfigured_raises_clean_error():
    provider = ArchiverApplianceProvider(ArchiverSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(ArchiverUnconfiguredError):
        await provider.get_data("QF12:CURRENT", datetime.now() - timedelta(hours=1), datetime.now())


@respx.mock
async def test_get_data_parses_samples():
    provider = _configured()
    respx.get("http://archiver.test/retrieval/data/getData.json").mock(
        return_value=httpx.Response(
            200,
            json=[{"data": [{"secs": 1700000000, "nanos": 0, "val": 4.2, "severity": 0}]}],
        )
    )
    series = await provider.get_data("QF12:CURRENT", datetime.now() - timedelta(hours=1), datetime.now())
    assert series.pv_name == "QF12:CURRENT"
    assert series.samples[0].value == 4.2


@respx.mock
async def test_get_data_translates_connection_error():
    provider = _configured()
    respx.get("http://archiver.test/retrieval/data/getData.json").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ArchiverUnavailableError):
        await provider.get_data("QF12:CURRENT", datetime.now() - timedelta(hours=1), datetime.now())


@respx.mock
async def test_get_data_unexpected_shape_raises_query_error():
    provider = _configured()
    # An empty list response means series[0] raises IndexError -> ArchiverQueryError.
    respx.get("http://archiver.test/retrieval/data/getData.json").mock(return_value=httpx.Response(200, json=[]))
    with pytest.raises(ArchiverQueryError):
        await provider.get_data("QF12:CURRENT", datetime.now() - timedelta(hours=1), datetime.now())
