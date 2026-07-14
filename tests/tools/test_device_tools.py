import json

from argus.mcp_server.server import build_registry


async def test_get_device_returns_device_metadata(app_context):
    registry = build_registry()
    response = await registry.dispatch("get_device", {"device_name": "QF12:CURRENT"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["device"]["name"] == "QF12:CURRENT"


async def test_diagnose_device_returns_structured_report(app_context):
    registry = build_registry()
    response = await registry.dispatch("diagnose_device", {"device_name": "QF12:CURRENT"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["live_pvs"]["status"] == "ok"  # QF12:CURRENT is a known fake_epics value
    assert payload["history"]["status"] == "unconfigured"  # archiver not configured in app_context
    assert "degraded_providers" in payload


async def test_get_device_missing_device_name_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("get_device", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_search_pvs_without_channelfinder_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("search_pvs", {"query": "QF12"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "channelfinder_error"
