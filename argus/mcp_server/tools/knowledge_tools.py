"""Config history and issue/ticket knowledge base tools, spanning GitHub and
GitLab. Read-only: no issue creation, no commenting, no commits — ARGUS can
surface past problems/solutions and config history, never write to a repo.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition

_REPO_URL_DESC = "A git URL, e.g. https://github.com/infn-epics/ioc-chart.git or https://baltig.infn.it/lnf-da-control/epik8s-btf.git"

_SEARCH_KB_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Free-text search query, e.g. 'BTF2 magnet interlock'."},
        "repos": {
            "type": "array",
            "items": {"type": "string"},
            "description": f"Repos to search. {_REPO_URL_DESC} Defaults to the configured repo list if omitted.",
        },
        "state": {
            "type": "string",
            "enum": ["all", "open", "closed"],
            "description": "Filter by issue state. Defaults to all.",
        },
    },
    "required": ["query"],
}

_CONFIG_HISTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "repo": {"type": "string", "description": _REPO_URL_DESC},
        "path": {"type": "string", "description": "File path within the repo, e.g. deploy/values.yaml."},
        "limit": {"type": "integer", "description": "Maximum number of commits to return. Defaults to 20."},
        "commit_sha": {
            "type": "string",
            "description": "If given, return this commit's diff instead of the file's commit history.",
        },
        "ref": {
            "type": "string",
            "description": (
                "If given (e.g. 'HEAD' for the current version, or a branch/tag/commit sha), return the "
                "file's full content at that ref instead of its commit history. Use this to read the "
                "current beamline inventory (IOCs, devices, zones, geo, devgroup/devtype, connection IPs) "
                "straight out of a config file like deploy/values.yaml."
            ),
        },
    },
    "required": ["repo", "path"],
}


async def _search_knowledge_base(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    query = arguments.get("query")
    if not query or not isinstance(query, str):
        raise ValidationError("query cannot be empty and must be a string.")

    issues = await ctx.knowledge_service.search_knowledge_base(
        query, repos=arguments.get("repos"), state=arguments.get("state", "all")
    )
    return {"issues": [dataclasses.asdict(i) for i in issues]}


async def _get_config_history(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    repo = arguments.get("repo")
    path = arguments.get("path")
    if not repo or not isinstance(repo, str):
        raise ValidationError("repo cannot be empty and must be a string.")
    if not path or not isinstance(path, str):
        raise ValidationError("path cannot be empty and must be a string.")

    commit_sha = arguments.get("commit_sha")
    if commit_sha:
        diff = await ctx.knowledge_service.get_commit_diff(repo, commit_sha)
        return {"commit_sha": commit_sha, "diff": [dataclasses.asdict(d) for d in diff]}

    ref = arguments.get("ref")
    if ref:
        file = await ctx.knowledge_service.get_file(repo, path, ref)
        return dataclasses.asdict(file)

    limit = arguments.get("limit", 20)
    history = await ctx.knowledge_service.get_config_history(repo, path, limit=limit)
    return {"history": [dataclasses.asdict(c) for c in history]}


TOOLS = [
    ToolDefinition(
        name="search_knowledge_base",
        description="Search issues/tickets across configured repos for past problems and how they were resolved.",
        input_schema=_SEARCH_KB_SCHEMA,
        handler=_search_knowledge_base,
    ),
    ToolDefinition(
        name="get_config_history",
        description=(
            "Read a config file from a beamline's deployment repo (pass ref='HEAD' for its current "
            "content), its git commit history, or a specific commit's diff. This is the source of truth "
            "for IOC/device inventory, zones, geo coordinates, devgroup/devtype classification (e.g. "
            "'mag' for magnets), and connection IPs/ports — e.g. deploy/values.yaml in a beamline's "
            "epik8s-btf-style repo. For live PV values/status of a device you already know the name of, "
            "use get_device/device_status/diagnose_device instead; ChannelFinder only resolves a known "
            "device name to its PVs, it doesn't enumerate devices by category."
        ),
        input_schema=_CONFIG_HISTORY_SCHEMA,
        handler=_get_config_history,
    ),
]
