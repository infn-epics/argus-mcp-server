"""Structured logging bootstrap.

JSON output when ``ARGUS_LOG_JSON`` is true (the default, suited for production
log aggregation), a readable console renderer otherwise (local development).
"""

from __future__ import annotations

import logging
import sys

import structlog

from argus.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    # stdout is reserved for the MCP JSON-RPC stream when running the stdio
    # transport — logging there would corrupt the protocol stream, so every
    # log line goes to stderr regardless of transport.
    logging.basicConfig(level=settings.log_level, format="%(message)s", stream=sys.stderr)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
