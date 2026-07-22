"""Per-tool-call correlation: extracts LibreChat's conversation/message/user
IDs from the MCP request's HTTP headers, when present, so argus-mcp-server's
own structured logs (see core/request_context.py) can be tied back to the
exact LibreChat conversation/message that triggered them.

LibreChat's MCP client refreshes these headers before every individual tool
call (not just once per SSE connection), and the mcp SDK captures the raw
HTTP request per JSON-RPC message and exposes it via Server.request_context
inside a @server.call_tool() handler — see argus-helm-chart's
librechat-configmap.yaml for where the headers themselves get set.

Only SSE/streamable-http transports carry a real HTTP request per call;
stdio transport (and any call made without these headers, e.g. a non-
LibreChat MCP client) yields an empty dict, which is a no-op for
request_scope().
"""

from __future__ import annotations

from typing import Any

from mcp.server import Server

_HEADER_TO_FIELD = {
    "x-librechat-conversation-id": "conversation_id",
    "x-librechat-message-id": "message_id",
    "x-librechat-user-id": "user_id",
}


def current_http_request(server: Server) -> Any | None:
    """The raw Starlette Request for the MCP call currently being handled, or
    None outside of an HTTP-transported call (stdio, or outside a request
    entirely)."""
    try:
        return server.request_context.request
    except LookupError:
        return None


def extract_correlation_headers(request: Any | None) -> dict[str, str]:
    if request is None:
        return {}
    headers = getattr(request, "headers", None)
    if headers is None:
        return {}
    result: dict[str, str] = {}
    for header_name, field in _HEADER_TO_FIELD.items():
        value = headers.get(header_name)
        if value:
            result[field] = value
    return result
