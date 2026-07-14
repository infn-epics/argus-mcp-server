"""Tool registration and the single error->structured-response dispatch boundary.

MCP tools orchestrate services; they never contain business logic themselves.
Every handler is `async def handler(arguments: dict, ctx: AppContext) -> dict`
returning the fields to merge into `{"status": "success", ...}` — the registry
takes care of JSON encoding, exceptions, and request-id/logging scope.
"""

from __future__ import annotations

import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog
from mcp.types import TextContent, Tool

from argus.core.context import AppContext
from argus.core.errors import ArgusError
from argus.core.request_context import request_scope

logger = structlog.get_logger(__name__)

ToolHandler = Callable[[dict[str, Any], AppContext], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def as_mcp_tool(self) -> Tool:
        return Tool(name=self.name, description=self.description, inputSchema=self.input_schema)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def register_many(self, tools: list[ToolDefinition]) -> None:
        for tool in tools:
            self.register(tool)

    def list_tools(self) -> list[Tool]:
        return [tool.as_mcp_tool() for tool in self._tools.values()]

    async def dispatch(self, name: str, arguments: dict[str, Any], ctx: AppContext) -> list[TextContent]:
        tool = self._tools.get(name)
        if tool is None:
            return [_error_response("unknown_tool", f"Unknown tool: {name}")]

        with request_scope():
            structlog.contextvars.bind_contextvars(tool=name)
            try:
                result = await tool.handler(arguments, ctx)
                return [_success_response(result)]
            except ArgusError as exc:
                logger.warning("tool_error", code=exc.code, error=str(exc))
                return [_error_response(exc.code, str(exc))]
            except NotImplementedError as exc:
                logger.info("tool_not_implemented", error=str(exc))
                return [_error_response("not_implemented", str(exc))]
            except Exception:
                logger.exception("tool_unexpected_error")
                return [_error_response("internal_error", "An internal error occurred.")]
            finally:
                structlog.contextvars.unbind_contextvars("tool")


def _json_default(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _sanitize(value: Any) -> Any:
    """Recursively replace NaN/Infinity with None — not valid JSON, would break strict parsers."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def _success_response(result: dict[str, Any]) -> TextContent:
    payload = _sanitize({"status": "success", **result})
    text = json.dumps(payload, indent=2, default=_json_default, allow_nan=False)
    return TextContent(type="text", text=text)


def _error_response(code: str, message: str) -> TextContent:
    payload = {"status": "error", "code": code, "message": message}
    return TextContent(type="text", text=json.dumps(payload, indent=2))
