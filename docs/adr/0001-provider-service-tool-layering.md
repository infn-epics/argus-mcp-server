# ADR 0001: Provider / Service / MCP-tool layering

## Status

Accepted.

## Context

The original epics-mcp-server had MCP tool handlers calling `pyepics`
directly — data access, protocol details, and response shaping all lived in
the same function. That's fine for 3 tools and one backend. ARGUS needs to
orchestrate 8 backends behind ~18 tools, degrade gracefully when any one of
them is unavailable, and stay extensible to future backends (Prometheus,
Grafana, InfluxDB, Kafka, OpenSearch, a Digital Twin) without rewriting
existing tools.

## Decision

Three strict layers:

- **Providers** (`argus/providers/`) only retrieve or mutate data from one
  external system. No cross-provider logic, no response shaping for the
  LLM — just a typed, async interface over that system's own client
  library/API.
- **Services** (`argus/services/`) hold all business logic: which providers
  to call, in what order, how to combine their results, how to degrade when
  one fails. Services depend on providers; they never depend on the MCP
  layer.
- **MCP tools** (`argus/mcp_server/tools/`) are thin: validate input, call
  exactly one service method, shape the JSON response. They contain no
  business logic and don't know which providers a service call touches.

## Consequences

- Adding a provider never requires touching a tool.
- Adding a tool never requires touching a provider.
- Testing a service means mocking providers, not the MCP protocol; testing a
  tool means using a fake `AppContext`, not real providers.
- The LLM only ever sees the tool layer, so "the tool decides whether data
  comes from EPICS, Archiver, Kubernetes, ..." (the spec's core requirement)
  falls out of the architecture rather than needing special-casing.
