from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_GET_HISTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "pv_name": {"type": "string", "description": "The PV to retrieve historical trend data for."},
        "start": {"type": "string", "description": "ISO 8601 start time. Defaults to 1 hour ago."},
        "end": {"type": "string", "description": "ISO 8601 end time. Defaults to now."},
    },
    "required": ["pv_name"],
}

_GET_ALARM_HISTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "device_name": {"type": "string", "description": "The device to retrieve recent alarm history for."},
    },
    "required": ["device_name"],
}


def _parse_time(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid ISO 8601 timestamp: {value!r}") from exc


async def _get_history(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    pv_name = arguments.get("pv_name")
    if not pv_name or not isinstance(pv_name, str):
        raise ValidationError("pv_name cannot be empty and must be a string.")

    now = datetime.now(timezone.utc)
    start = _parse_time(arguments.get("start"), now - timedelta(hours=1))
    end = _parse_time(arguments.get("end"), now)

    series = await ctx.history_service.get_history(pv_name, start, end)
    return {"history": dataclasses.asdict(series)}


async def _get_alarm_history(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    device_name = arguments.get("device_name")
    if not device_name or not isinstance(device_name, str):
        raise ValidationError("device_name cannot be empty and must be a string.")

    entries = await ctx.history_service.get_alarm_history(device_name)
    return {"entries": [dataclasses.asdict(e) for e in entries]}


TOOLS = [
    ToolDefinition(
        name="get_history",
        description="Get historical trend data for a PV over a time range (from the Archiver Appliance).",
        input_schema=_GET_HISTORY_SCHEMA,
        handler=_get_history,
    ),
    ToolDefinition(
        name="get_alarm_history",
        description="Get recent alarm-tagged logbook entries for a device.",
        input_schema=_GET_ALARM_HISTORY_SCHEMA,
        handler=_get_alarm_history,
    ),
]
