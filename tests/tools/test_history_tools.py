import json

import httpx
import respx

from argus.mcp_server.server import build_registry


async def test_create_logbook_entry_missing_title_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "create_logbook_entry", {"text": "body", "logbooks": ["operations"]}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_create_logbook_entry_missing_logbooks_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "create_logbook_entry", {"title": "t", "text": "body"}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_create_logbook_entry_unconfigured_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "create_logbook_entry",
        {"title": "t", "text": "body", "logbooks": ["operations"]},
        app_context,
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "logbook_unconfigured"


@respx.mock
async def test_create_logbook_entry_success(app_context):
    app_context.logbook._settings.base_url = "http://olog.test"
    respx.put("http://olog.test/Olog/logs").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 1,
                "title": "t",
                "description": "body",
                "logbooks": [{"name": "operations"}],
                "tags": [],
                "owner": "shift-crew",
            },
        )
    )
    registry = build_registry()
    response = await registry.dispatch(
        "create_logbook_entry",
        {"title": "t", "text": "body", "logbooks": ["operations"]},
        app_context,
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["title"] == "t"
    assert payload["logbooks"] == ["operations"]
