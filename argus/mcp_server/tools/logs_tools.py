from __future__ import annotations

import dataclasses
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


async def _get_logs(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValidationError("query cannot be empty and must be a string.")

    limit = arguments.get("limit", 100)
    records = await ctx.history_service.get_logs(query, index=arguments.get("index"), limit=limit)
    return {"logs": [dataclasses.asdict(r) for r in records]}


TOOLS = [
    ToolDefinition(
        name="get_logs",
        description="Search historical application/IOC logs in Elasticsearch.",
        input_schema=_GET_LOGS_SCHEMA,
        handler=_get_logs,
    ),
]
