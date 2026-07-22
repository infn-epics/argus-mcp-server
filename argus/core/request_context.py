"""Request-id plumbing threaded through every MCP tool call via contextvars."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


@contextmanager
def request_scope(request_id: str | None = None, extra: dict[str, str] | None = None) -> Iterator[str]:
    """Bind a request id (and optional extra fields) to the current context and
    to structlog's contextvars.

    Every log line emitted while inside this scope (including provider_call
    events logged deep in gather_with_timeout) automatically carries request_id
    and whatever ``extra`` was passed — e.g. LibreChat's conversation_id/
    message_id/user_id, when the MCP call carried them as headers (see
    mcp_server/server.py's handle_call_tool), so a Loki query for one bad-rated
    conversation shows every tool-call log line it triggered.
    """
    rid = request_id or new_request_id()
    token = request_id_var.set(rid)
    bound = {"request_id": rid, **(extra or {})}
    structlog.contextvars.bind_contextvars(**bound)
    try:
        yield rid
    finally:
        request_id_var.reset(token)
        structlog.contextvars.unbind_contextvars(*bound.keys())
