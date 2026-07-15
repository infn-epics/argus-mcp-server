from __future__ import annotations

import dataclasses
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_SEARCH_PVS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "PV name pattern, tag, or property to search for."},
        "limit": {"type": "integer", "description": "Maximum number of results to return."},
    },
    "required": ["query"],
}

_NAMESPACE_SCHEMA = {
    "type": "object",
    "properties": {
        "namespace": {"type": "string", "description": "Kubernetes namespace. Defaults to the configured default."},
    },
    "required": [],
}

_RESTART_IOC_SCHEMA = {
    "type": "object",
    "properties": {
        "pod_name": {"type": "string", "description": "The Kubernetes pod name of the IOC to restart."},
        "namespace": {"type": "string", "description": "Kubernetes namespace the pod runs in."},
    },
    "required": ["pod_name", "namespace"],
}

_EXECUTE_PROCEDURE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "The name of the pre-approved operational procedure to run."},
        "params": {"type": "object", "description": "Parameters for the procedure."},
    },
    "required": ["name"],
}


async def _search_pvs(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValidationError("query cannot be empty and must be a string.")
    channels = await ctx.operations_service.search_pvs(query, limit=arguments.get("limit", 50))
    return {"channels": [dataclasses.asdict(c) for c in channels]}


async def _list_iocs(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    pods = await ctx.operations_service.list_iocs(namespace=arguments.get("namespace"))
    return {"iocs": [dataclasses.asdict(p) for p in pods]}


async def _restart_ioc(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    pod_name = arguments.get("pod_name")
    namespace = arguments.get("namespace")
    if not pod_name or not isinstance(pod_name, str):
        raise ValidationError("pod_name cannot be empty and must be a string.")
    if not namespace or not isinstance(namespace, str):
        raise ValidationError("namespace cannot be empty and must be a string.")

    accepted = await ctx.operations_service.restart_ioc(pod_name, namespace)
    return {"restarted": accepted, "pod_name": pod_name, "namespace": namespace}


async def _execute_procedure(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    name = arguments.get("name")
    if not name or not isinstance(name, str):
        raise ValidationError("name cannot be empty and must be a string.")
    result = await ctx.operations_service.execute_procedure(name, arguments.get("params", {}))
    return {"result": result}


async def _machine_summary(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    summary = await ctx.operations_service.machine_summary(namespace=arguments.get("namespace"))
    return dataclasses.asdict(summary)


TOOLS = [
    ToolDefinition(
        name="search_pvs",
        description=(
            "Search PVs/channels already registered in ChannelFinder by name pattern, tag, or property. "
            "This does not enumerate devices by category or beamline/zone (e.g. 'all quadrupoles in "
            "BTF1') — ChannelFinder's naming/tagging doesn't necessarily match device-type words. To "
            "discover what devices exist in a beamline/zone (including their type, e.g. magnets, "
            "quadrupoles), use list_beamline_devices first; use search_pvs afterwards only to resolve "
            "specific already-known PVs."
        ),
        input_schema=_SEARCH_PVS_SCHEMA,
        handler=_search_pvs,
    ),
    ToolDefinition(
        name="list_iocs",
        description="List running IOCs and their Kubernetes pod status.",
        input_schema=_NAMESPACE_SCHEMA,
        handler=_list_iocs,
    ),
    ToolDefinition(
        name="restart_ioc",
        description="Restart an IOC's pod.",
        input_schema=_RESTART_IOC_SCHEMA,
        handler=_restart_ioc,
    ),
    ToolDefinition(
        name="machine_summary",
        description="High-level machine-wide summary: IOC health counts and recent alarm count.",
        input_schema=_NAMESPACE_SCHEMA,
        handler=_machine_summary,
    ),
    ToolDefinition(
        name="execute_procedure",
        description="Run a named, pre-approved operational procedure.",
        input_schema=_EXECUTE_PROCEDURE_SCHEMA,
        handler=_execute_procedure,
    ),
]
