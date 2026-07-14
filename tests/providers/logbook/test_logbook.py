import httpx
import pytest
import respx

from argus.config.settings import LogbookSettings
from argus.providers.logbook.exceptions import LogbookUnavailableError, LogbookUnconfiguredError
from argus.providers.logbook.logbook import LogbookProvider


def _configured() -> LogbookProvider:
    return LogbookProvider(LogbookSettings(_env_file=None, LOGBOOK_BASE_URL="http://olog.test"))


async def test_unconfigured_raises_clean_error():
    provider = LogbookProvider(LogbookSettings(_env_file=None))
    with pytest.raises(LogbookUnconfiguredError):
        await provider.search_entries(text="QF12")


@respx.mock
async def test_search_entries_parses_payload():
    provider = _configured()
    respx.get("http://olog.test/Olog/logs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "title": "QF12 tripped",
                    "description": "Overcurrent alarm",
                    "logbooks": [{"name": "operations"}],
                    "tags": [{"name": "alarm"}],
                    "owner": "shift-crew",
                }
            ],
        )
    )
    entries = await provider.search_entries(text="QF12", tags=["alarm"])
    assert entries[0].title == "QF12 tripped"
    assert entries[0].logbooks == ["operations"]
    assert entries[0].tags == ["alarm"]


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.get("http://olog.test/Olog/logs").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(LogbookUnavailableError):
        await provider.search_entries(text="QF12")
