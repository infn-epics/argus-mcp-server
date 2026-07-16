import json

import httpx
import respx

from argus.mcp_server.server import build_registry


def _configure(app_context):
    app_context.saverestore._settings.base_url = "http://snr.test/save-restore"


async def test_search_snapshots_missing_query_and_node_id_returns_validation_error(app_context):
    _configure(app_context)
    registry = build_registry()
    response = await registry.dispatch("search_snapshots", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_search_snapshots_unconfigured_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("search_snapshots", {"query": "MAGNET_SP"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "saverestore_unconfigured"


@respx.mock
async def test_search_snapshots_by_query(app_context):
    _configure(app_context)
    respx.get("http://snr.test/save-restore/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "hitCount": 1,
                "nodes": [
                    {
                        "uniqueId": "c896c0d3",
                        "name": "MAGNET_SP",
                        "nodeType": "CONFIGURATION",
                        "created": 1783526208460,
                        "lastModified": 1783593957372,
                        "userName": "shift-crew",
                    }
                ],
            },
        )
    )
    registry = build_registry()
    response = await registry.dispatch("search_snapshots", {"query": "MAGNET_SP"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["nodes"][0]["name"] == "MAGNET_SP"


@respx.mock
async def test_search_snapshots_by_node_id_lists_children(app_context):
    _configure(app_context)
    respx.get("http://snr.test/save-restore/node/folder-id/children").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "uniqueId": "child-1",
                    "name": "MAGNET_SP",
                    "nodeType": "CONFIGURATION",
                    "created": None,
                    "lastModified": None,
                    "userName": "shift-crew",
                }
            ],
        )
    )
    registry = build_registry()
    response = await registry.dispatch("search_snapshots", {"node_id": "folder-id"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["nodes"][0]["name"] == "MAGNET_SP"


@respx.mock
async def test_get_snapshot_for_configuration_node(app_context):
    _configure(app_context)
    respx.get("http://snr.test/save-restore/node/cfg-id").mock(
        return_value=httpx.Response(
            200,
            json={
                "uniqueId": "cfg-id",
                "name": "MAGNET_SP",
                "nodeType": "CONFIGURATION",
                "created": None,
                "lastModified": None,
                "userName": "shift-crew",
            },
        )
    )
    respx.get("http://snr.test/save-restore/config/cfg-id").mock(
        return_value=httpx.Response(
            200,
            json={
                "uniqueId": "cfg-id",
                "pvList": [{"pvName": "BTF:MAG:QUATB201:CURRENT_SP", "readbackPvName": None, "readOnly": False}],
            },
        )
    )
    registry = build_registry()
    response = await registry.dispatch("get_snapshot", {"node_id": "cfg-id"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert "configuration" in payload
    assert payload["configuration"]["pv_list"][0]["pv_name"] == "BTF:MAG:QUATB201:CURRENT_SP"


@respx.mock
async def test_get_snapshot_for_folder_node_returns_hint(app_context):
    _configure(app_context)
    respx.get("http://snr.test/save-restore/node/folder-id").mock(
        return_value=httpx.Response(
            200,
            json={
                "uniqueId": "folder-id",
                "name": "BTF_CONF",
                "nodeType": "FOLDER",
                "created": None,
                "lastModified": None,
                "userName": "shift-crew",
            },
        )
    )
    registry = build_registry()
    response = await registry.dispatch("get_snapshot", {"node_id": "folder-id"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert "message" in payload
