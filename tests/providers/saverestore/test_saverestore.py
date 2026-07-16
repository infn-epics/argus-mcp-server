import httpx
import pytest
import respx

from argus.config.settings import SaveRestoreSettings
from argus.providers.saverestore.exceptions import SaveRestoreUnavailableError, SaveRestoreUnconfiguredError
from argus.providers.saverestore.saverestore import SaveRestoreProvider

# Payload shapes below mirror real responses captured live against a running
# Phoebus save-and-restore deployment (epik8s-btf, namespace btf) -- not
# assumed from docs.

_SEARCH_PAYLOAD = {
    "hitCount": 2,
    "nodes": [
        {
            "uniqueId": "2b878197-1640-4f6e-83f5-d07907ec5163",
            "name": "BTF_CONF",
            "description": None,
            "created": 1783526128387,
            "lastModified": 1783526269079,
            "nodeType": "FOLDER",
            "userName": "shift-crew",
        },
        {
            "uniqueId": "c896c0d3-0a7a-4188-8bf7-d87daaaa3223",
            "name": "MAGNET_SP",
            "description": "MAGNET_SP",
            "created": 1783526208460,
            "lastModified": 1783593957372,
            "nodeType": "CONFIGURATION",
            "userName": "shift-crew",
        },
    ],
}

_CONFIG_PAYLOAD = {
    "uniqueId": "c896c0d3-0a7a-4188-8bf7-d87daaaa3223",
    "pvList": [
        {
            "pvName": "BTF:MAG:EEI:QUATB201:CURRENT_SP",
            "readbackPvName": "BTF:MAG:EEI:QUATB201:CURRENT_RB",
            "readOnly": False,
            "comparison": None,
        }
    ],
}

_SNAPSHOT_PAYLOAD = {
    "uniqueId": "e03d5f67-7c12-4974-af8b-9f115264ca5f",
    "snapshotItems": [
        {
            "configPv": {
                "pvName": "BTF:MAG:EEI:QUATB201:CURRENT_SP",
                "readbackPvName": "BTF:MAG:EEI:QUATB201:CURRENT_RB",
                "readOnly": False,
            },
            "value": {
                "type": {"name": "VDouble", "version": 1},
                "value": 0.0,
                "alarm": {"severity": "NONE", "status": "NONE", "name": "NO_ALARM"},
                "time": {"unixSec": 1783526307, "nanoSec": 617425936},
                "display": {"lowDisplay": -330000.0, "highDisplay": 100.0, "units": "A"},
            },
            "readbackValue": {
                "type": {"name": "VDouble", "version": 1},
                "value": 0.0,
                "alarm": {"severity": "NONE", "status": "NONE", "name": "NO_ALARM"},
                "time": {"unixSec": 1783528066, "nanoSec": 146481054},
                "display": {"lowDisplay": 0.0, "highDisplay": 0.0, "units": "A"},
            },
        }
    ],
}


def _configured() -> SaveRestoreProvider:
    return SaveRestoreProvider(SaveRestoreSettings(_env_file=None, SAVERESTORE_BASE_URL="http://snr.test/save-restore"))


async def test_unconfigured_raises_clean_error():
    provider = SaveRestoreProvider(SaveRestoreSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(SaveRestoreUnconfiguredError):
        await provider.search("MAGNET_SP")


@respx.mock
async def test_search_parses_nodes():
    provider = _configured()
    respx.get("http://snr.test/save-restore/search").mock(return_value=httpx.Response(200, json=_SEARCH_PAYLOAD))
    nodes = await provider.search("MAGNET_SP")
    assert len(nodes) == 2
    assert nodes[0].node_type == "FOLDER"
    assert nodes[1].node_type == "CONFIGURATION"
    assert nodes[1].name == "MAGNET_SP"


@respx.mock
async def test_get_configuration_parses_pv_list():
    provider = _configured()
    respx.get("http://snr.test/save-restore/config/c896c0d3-0a7a-4188-8bf7-d87daaaa3223").mock(
        return_value=httpx.Response(200, json=_CONFIG_PAYLOAD)
    )
    config = await provider.get_configuration("c896c0d3-0a7a-4188-8bf7-d87daaaa3223")
    assert config.pv_list[0].pv_name == "BTF:MAG:EEI:QUATB201:CURRENT_SP"
    assert config.pv_list[0].readback_pv_name == "BTF:MAG:EEI:QUATB201:CURRENT_RB"


@respx.mock
async def test_get_snapshot_parses_values():
    provider = _configured()
    respx.get("http://snr.test/save-restore/snapshot/e03d5f67-7c12-4974-af8b-9f115264ca5f").mock(
        return_value=httpx.Response(200, json=_SNAPSHOT_PAYLOAD)
    )
    snapshot = await provider.get_snapshot("e03d5f67-7c12-4974-af8b-9f115264ca5f")
    item = snapshot.items[0]
    assert item.pv_name == "BTF:MAG:EEI:QUATB201:CURRENT_SP"
    assert item.value == 0.0
    assert item.readback_value == 0.0
    assert item.units == "A"
    assert item.severity == "NONE"


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.get("http://snr.test/save-restore/search").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(SaveRestoreUnavailableError):
        await provider.search("MAGNET_SP")
