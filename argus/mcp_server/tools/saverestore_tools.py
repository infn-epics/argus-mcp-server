"""Phoebus save-and-restore tools. Read-only: search/browse saved
configurations and snapshots and read their PV values, but never apply
(restore) a snapshot — see providers/saverestore/saverestore.py for why.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_SEARCH_SNAPSHOTS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Free-text search across all folders/configurations/snapshots, e.g. a configuration name "
                "like 'MAGNET_SP'. Omit and pass node_id instead to list a specific folder's children."
            ),
        },
        "node_id": {
            "type": "string",
            "description": "A folder node's uniqueId (from a previous search_snapshots call) to list its direct children instead of searching.",
        },
    },
}

_GET_SNAPSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "node_id": {
            "type": "string",
            "description": "A CONFIGURATION or SNAPSHOT node's uniqueId, from search_snapshots.",
        },
    },
    "required": ["node_id"],
}


async def _search_snapshots(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    node_id = arguments.get("node_id")
    if node_id:
        nodes = await ctx.saverestore_service.get_children(node_id)
        return {"nodes": [dataclasses.asdict(n) for n in nodes]}

    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValidationError("Provide either query (to search) or node_id (to list a folder's children).")
    nodes = await ctx.saverestore_service.search(query)
    return {"nodes": [dataclasses.asdict(n) for n in nodes]}


async def _get_snapshot(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    node_id = arguments.get("node_id")
    if not node_id or not isinstance(node_id, str):
        raise ValidationError("node_id cannot be empty and must be a string.")

    node = await ctx.saverestore_service.get_node(node_id)
    if node.node_type == "SNAPSHOT":
        snapshot = await ctx.saverestore_service.get_snapshot(node_id)
        return {"node": dataclasses.asdict(node), "snapshot": dataclasses.asdict(snapshot)}
    if node.node_type == "CONFIGURATION":
        config = await ctx.saverestore_service.get_configuration(node_id)
        return {"node": dataclasses.asdict(node), "configuration": dataclasses.asdict(config)}
    return {
        "node": dataclasses.asdict(node),
        "message": "This is a FOLDER node — use search_snapshots with node_id set to this id to list its children.",
    }


TOOLS = [
    ToolDefinition(
        name="search_snapshots",
        description=(
            "Search or browse Phoebus save-and-restore: pass query for free-text search across all "
            "folders/configurations/snapshots, or node_id (a folder's uniqueId from a previous result) to "
            "list that folder's direct children. A CONFIGURATION defines which PVs a snapshot covers; a "
            "SNAPSHOT is a saved set of PV values at a point in time. Use the returned uniqueId with "
            "get_snapshot to read a configuration's PV list or a snapshot's saved values. Read-only: "
            "ARGUS can read saved configurations/snapshots but cannot restore (apply) one back to live PVs."
        ),
        input_schema=_SEARCH_SNAPSHOTS_SCHEMA,
        handler=_search_snapshots,
    ),
    ToolDefinition(
        name="get_snapshot",
        description=(
            "Get the detail of a save-and-restore node by its uniqueId (from search_snapshots): a "
            "CONFIGURATION's PV list (which PVs/readback PVs it covers, not their values), or a "
            "SNAPSHOT's saved PV values and readback values as of when it was taken."
        ),
        input_schema=_GET_SNAPSHOT_SCHEMA,
        handler=_get_snapshot,
    ),
]
