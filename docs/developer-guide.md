# Developer Guide

## Local setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # fill in EPICS_CA_ADDR_LIST at minimum
.venv/bin/pytest
```

Run the server directly:

```bash
.venv/bin/python -m argus --transport stdio
.venv/bin/python -m argus --transport sse --host 0.0.0.0 --port 8000
```

Tests never require a running EPICS/Kubernetes/ArgoCD/etc. instance — every
provider is exercised through mocks (`respx` for HTTP providers, monkeypatched
`aioca`/`kubernetes.config` for EPICS/Kubernetes). If you want to test against
a real IOC locally: `softIoc -d some.db` (EPICS base), then set
`EPICS_CA_ADDR_LIST=127.0.0.1` in `.env`.

## Adding a new provider

Providers only retrieve/mutate data — no orchestration logic. Follow the
existing pattern (e.g. `providers/archiver/`):

1. `providers/<name>/models.py` — small dataclasses for whatever the provider
   returns. Never return raw dicts from a provider method.
2. `providers/<name>/exceptions.py` — a root `<Name>Error(ArgusError)`, plus
   `<Name>UnconfiguredError`/`<Name>UnavailableError`/`<Name>TimeoutError`
   subclassing both `<Name>Error` and the matching `Provider*Error` in
   `core/errors.py` (this dual inheritance is what lets `gather_with_timeout`
   classify the failure generically *and* lets callers catch the
   provider-specific type).
3. `providers/<name>/<name>.py` — the concrete adapter. Implement
   `is_configured()` (cheap, no I/O) and `health()`. Every domain method
   should call a `_require_configured()` guard first.
4. `config/settings.py` — add a `<Name>Settings(_ProviderSettings)` with all
   fields optional, and add it to `Settings`.
5. `core/context.py` — construct the provider in `AppContext.build()` and
   inject it into whichever service(s) need it.
6. `tests/providers/<name>/test_<name>.py` — at minimum: unconfigured raises
   the clean error, one happy-path parse test, one unreachable-backend test.

No existing service or tool needs to change unless the new provider is meant
to feed one of them — that's the point of the provider/service/tool split.

## Adding a new tool

Tools orchestrate services; they hold no business logic.

1. Add a handler `async def _my_tool(arguments: dict, ctx: AppContext) -> dict`
   in the relevant `mcp_server/tools/*.py` (or a new file if it's a new
   category). Validate arguments and raise `ValidationError` on bad input;
   call exactly one service method; shape the return dict.
2. Add a `ToolDefinition(name=..., description=..., input_schema=..., handler=...)`
   to that module's `TOOLS` list.
3. Register the module's `TOOLS` in `mcp_server/server.py::build_registry()`
   if it's a new file.
4. Keep the total tool count in the ~15-20 band — this is a design
   constraint the LLM's tool selection depends on, not just a suggestion.
   `tests/tools/test_pv_tools_backward_compat.py::test_tool_count_is_within_high_level_target_band`
   enforces it.

## Conventions worth knowing

- **`from __future__ import annotations`** everywhere — keeps modern union
  syntax (`X | None`) usable regardless of the runtime Python version.
- **`gather_with_timeout`** (`core/models.py`) is the only place provider
  fan-out should happen. It's also the single point where
  `provider`/`backend`/`latency_ms`/`status` get logged, so don't add ad hoc
  logging around individual provider calls in services.
- **stdout is reserved** for the MCP JSON-RPC stream under the stdio
  transport. All logging goes to stderr (`config/logging.py`) — never
  `print()` from provider/service code.
- **No caching of live PV values**, ever. Everything else may be cached with
  an explicit TTL in `config/settings.py::CacheSettings`.
