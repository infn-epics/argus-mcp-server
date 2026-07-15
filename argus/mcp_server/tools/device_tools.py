"""Device-centric tools: the flagship diagnose_device()/device_status() flows,
plain device metadata lookup, and a beamline-wide status rollup.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_DEVICE_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "device_name": {
            "type": "string",
            "description": "The name of the device (e.g. a quadrupole, IOC, or bare PV name).",
        }
    },
    "required": ["device_name"],
}

_BEAMLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "beamline": {
            "type": "string",
            "description": "Beamline or device-group name to search for and roll up status across.",
        }
    },
    "required": ["beamline"],
}


def _require_device_name(arguments: dict[str, Any]) -> str:
    device_name = arguments.get("device_name")
    if not device_name or not isinstance(device_name, str):
        raise ValidationError("device_name cannot be empty and must be a string.")
    return device_name


async def _get_device(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    device_name = _require_device_name(arguments)
    device = await ctx.device_service.resolve_device(device_name)
    return {"device": dataclasses.asdict(device)}


async def _device_status(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    device_name = _require_device_name(arguments)
    report = await ctx.diagnostics_service.device_status(device_name)
    return dataclasses.asdict(report)


async def _diagnose_device(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    device_name = _require_device_name(arguments)
    report = await ctx.diagnostics_service.diagnose_device(device_name)
    return dataclasses.asdict(report)


async def _beamline_status(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    beamline = arguments.get("beamline")
    if not beamline or not isinstance(beamline, str):
        raise ValidationError("beamline cannot be empty and must be a string.")

    devices = await ctx.device_service.search_devices(beamline)
    reports = await asyncio.gather(
        *(ctx.diagnostics_service.device_status(device.name) for device in devices),
        return_exceptions=True,
    )

    summaries = []
    for device, report in zip(devices, reports, strict=True):
        if isinstance(report, BaseException):
            summaries.append({"device": device.name, "status": "error", "error": str(report)})
        else:
            summaries.append(
                {
                    "device": device.name,
                    "live_pvs": report.live_pvs.status,
                    "pod": report.pod.status,
                    "degraded_providers": report.degraded_providers,
                }
            )

    return {"beamline": beamline, "device_count": len(devices), "devices": summaries}


TOOLS = [
    ToolDefinition(
        name="get_device",
        description="Get full device metadata: PVs, IOC, pod, namespace, rack, owner, docs.",
        input_schema=_DEVICE_NAME_SCHEMA,
        handler=_get_device,
    ),
    ToolDefinition(
        name="device_status",
        description="Quick health snapshot of a device: live PV values and pod status.",
        input_schema=_DEVICE_NAME_SCHEMA,
        handler=_device_status,
    ),
    ToolDefinition(
        name="diagnose_device",
        description=(
            "Full cross-system diagnostic report for a device: live PVs, history, pod, "
            "pod logs, ArgoCD state, recent logbook entries, and documentation — one call."
        ),
        input_schema=_DEVICE_NAME_SCHEMA,
        handler=_diagnose_device,
    ),
    ToolDefinition(
        name="beamline_status",
        description=(
            "DO NOT use this to discover what devices/quadrupoles/magnets exist in a beamline or zone "
            "(e.g. 'magnets on BTF1') — use list_beamline_devices for that, first. This tool only rolls "
            "up live status (PVs + pod health) for devices whose ChannelFinder channel name matches "
            "'beamline', a fan-out over already-identified devices that can be slow on a broad match, and "
            "'beamline' here is a ChannelFinder name-match string, not a zone from the deploy YAML."
        ),
        input_schema=_BEAMLINE_SCHEMA,
        handler=_beamline_status,
    ),
]
