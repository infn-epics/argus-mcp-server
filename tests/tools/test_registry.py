import json

import structlog.contextvars

from argus.mcp_server.tools.registry import ToolDefinition, ToolRegistry


async def test_dispatch_binds_correlation_fields_during_handler_execution(app_context):
    captured = {}

    async def _handler(arguments, ctx):
        captured.update(structlog.contextvars.get_contextvars())
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="probe", description="", input_schema={}, handler=_handler))

    response = await registry.dispatch(
        "probe", {}, app_context, correlation={"conversation_id": "conv-1", "user_id": "user-1"}
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert captured["conversation_id"] == "conv-1"
    assert captured["user_id"] == "user-1"
    assert captured["tool"] == "probe"


async def test_dispatch_without_correlation_binds_no_extra_fields(app_context):
    captured = {}

    async def _handler(arguments, ctx):
        captured.update(structlog.contextvars.get_contextvars())
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(ToolDefinition(name="probe", description="", input_schema={}, handler=_handler))

    await registry.dispatch("probe", {}, app_context)
    assert "conversation_id" not in captured
    assert captured["tool"] == "probe"
