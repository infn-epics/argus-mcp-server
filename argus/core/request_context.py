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
def request_scope(request_id: str | None = None) -> Iterator[str]:
    """Bind a request id to the current context and to structlog's contextvars.

    Every log line emitted while inside this scope (including provider_call
    events logged deep in gather_with_timeout) automatically carries request_id.
    """
    rid = request_id or new_request_id()
    token = request_id_var.set(rid)
    structlog.contextvars.bind_contextvars(request_id=rid)
    try:
        yield rid
    finally:
        request_id_var.reset(token)
        structlog.contextvars.unbind_contextvars("request_id")
