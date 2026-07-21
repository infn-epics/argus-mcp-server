from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_GET_LOGS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query (Elasticsearch query_string syntax)."},
        "index": {"type": "string", "description": "Index to search. Defaults to the configured default index."},
        "limit": {"type": "integer", "description": "Maximum number of log records to return."},
    },
    "required": ["query"],
}

_SEARCH_POD_LOGS_SCHEMA = {
    "type": "object",
    "properties": {
        "namespace": {
            "type": "string",
            "description": "Kubernetes namespace to search. Omit to search across all namespaces.",
        },
        "pod": {
            "type": "string",
            "description": "Exact pod name to search. Omit to search across all pods matching the other filters.",
        },
        "container": {"type": "string", "description": "Exact container name to search."},
        "query": {"type": "string", "description": "Free-text substring filter applied to log lines."},
        "since_minutes": {
            "type": "integer",
            "description": "How far back to search, in minutes. Defaults to 60.",
        },
        "limit": {"type": "integer", "description": "Maximum number of log lines to return. Defaults to 200."},
    },
    "required": [],
}


async def _get_logs(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValidationError("query cannot be empty and must be a string.")

    limit = arguments.get("limit", 100)
    records = await ctx.history_service.get_logs(query, index=arguments.get("index"), limit=limit)
    return {"logs": [dataclasses.asdict(r) for r in records]}


async def _search_pod_logs(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    since_minutes = arguments.get("since_minutes", 60)
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    entries = await ctx.history_service.search_pod_logs(
        namespace=arguments.get("namespace"),
        pod=arguments.get("pod"),
        container=arguments.get("container"),
        query=arguments.get("query"),
        since=since,
        limit=arguments.get("limit", 200),
    )
    return {"logs": [dataclasses.asdict(e) for e in entries]}


TOOLS = [
    ToolDefinition(
        name="get_logs",
        description=(
            "Search historical application/IOC logs in Elasticsearch — a separate system from live "
            "Kubernetes pod logs, use search_pod_logs instead for pod/container log history."
        ),
        input_schema=_GET_LOGS_SCHEMA,
        handler=_get_logs,
    ),
    ToolDefinition(
        name="search_pod_logs",
        description=(
            "Search Kubernetes pod log history in Loki (7-day retention, survives pod restarts) by "
            "namespace/pod/container and an optional free-text filter. Defaults to the last 60 minutes "
            "across all namespaces/pods when no filters are given — pass at least namespace or pod to "
            "narrow it down for anything but a broad 'what's been happening lately' sweep. For a "
            "specific device/IOC's own recent logs, prefer diagnose_device instead — it already "
            "resolves the device's pod automatically and includes this alongside live PVs, ArgoCD "
            "state, and history in one call."
        ),
        input_schema=_SEARCH_POD_LOGS_SCHEMA,
        handler=_search_pod_logs,
    ),
]
