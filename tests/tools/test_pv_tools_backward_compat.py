"""Locks the exact tool name/schema/response-shape contract of the original
3-tool server (src/epics-mcp-server/server_by_stdio.py) so existing clients
(test/langchain_mcp_client_*.py) keep working unmodified against the new
argus package.
"""

from __future__ import annotations

import json

from argus.mcp_server.server import build_registry

# Copied verbatim from the pre-rewrite server_by_stdio.py Tool definitions.
_LEGACY_GET_PV_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "pv_name": {
            "type": "string",
            "description": "The name of the PV variable provided by the user.",
        }
    },
    "required": ["pv_name"],
}

_LEGACY_SET_PV_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "pv_name": {
            "type": "string",
            "description": "The name of the PV variable provided by the user.",
        },
        "pv_value": {
            "type": "string",
            "description": "The new PV value provided by the user.",
        },
    },
    "required": ["pv_name", "pv_value"],
}

_LEGACY_GET_PV_INFO_SCHEMA = _LEGACY_GET_PV_VALUE_SCHEMA


def _tool_by_name(name: str):
    registry = build_registry()
    tools = {t.name: t for t in registry.list_tools()}
    return tools[name]


def test_get_pv_value_schema_matches_legacy():
    tool = _tool_by_name("get_pv_value")
    assert tool.description == "Get the value of a specific PV."
    assert tool.inputSchema == _LEGACY_GET_PV_VALUE_SCHEMA


def test_set_pv_value_schema_matches_legacy():
    tool = _tool_by_name("set_pv_value")
    assert tool.description == "Set the value of a specific PV."
    assert tool.inputSchema == _LEGACY_SET_PV_VALUE_SCHEMA


def test_get_pv_info_schema_matches_legacy():
    tool = _tool_by_name("get_pv_info")
    assert tool.inputSchema == _LEGACY_GET_PV_INFO_SCHEMA


async def test_get_pv_value_call_returns_legacy_shape(app_context):
    registry = build_registry()
    response = await registry.dispatch("get_pv_value", {"pv_name": "QF12:CURRENT"}, app_context)
    payload = json.loads(response[0].text)
    assert payload == {"status": "success", "value": 4.2}


async def test_set_pv_value_call_returns_legacy_shape(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "set_pv_value", {"pv_name": "QF12:CURRENT", "pv_value": "5.0"}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload == {
        "status": "success",
        "message": "Successfully set PV 'QF12:CURRENT' value to: 5.0",
    }


async def test_get_pv_value_missing_pv_name_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("get_pv_value", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert "message" in payload


async def test_registered_tool_names_are_unique():
    registry = build_registry()
    names = [t.name for t in registry.list_tools()]
    assert len(names) == len(set(names))


async def test_tool_count_is_within_high_level_target_band():
    registry = build_registry()
    # ~15-20 high-level tools per the ARGUS design goal — not hundreds of
    # low-level per-backend tools.
    assert 15 <= len(registry.list_tools()) <= 20
