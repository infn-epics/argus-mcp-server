# ARGUS

ARGUS is an MCP server that gives an AI assistant a **unified operational
interface** to an accelerator control room — not just EPICS. A single tool
call like `diagnose_device("QF12")` transparently pulls together live PV
values, archived trends, Kubernetes pod status, ArgoCD deployment state,
recent logbook entries, and documentation, and returns one structured
report. The LLM never needs to know (or ask) which backend answered.

ARGUS started as a fork of INFN's `epics-mcp-server` (a 3-tool EPICS-only
proof of concept) and has been rebuilt into a modular
**provider → service → tool** architecture. See
[docs/architecture.md](docs/architecture.md) for the full picture.

## Why not just expose EPICS functions as tools?

Because a control room isn't just PVs. A device like quadrupole QF12 is a
PV group, an IOC, a Kubernetes pod, a GitOps deployment, a maintenance
history, and a stack of documentation — and answering "what's wrong with
QF12?" means correlating all of that. ARGUS exposes ~18 high-level,
intent-shaped tools instead of hundreds of thin per-backend wrappers; each
tool decides internally which of EPICS, the Archiver Appliance,
ChannelFinder, Kubernetes, ArgoCD, Elasticsearch, the electronic logbook, or
local documentation to query (in parallel, with per-backend timeouts and
graceful degradation).

## Quickstart

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # at minimum, set EPICS_CA_ADDR_LIST
.venv/bin/python -m argus --transport stdio
```

Every provider besides EPICS is entirely optional — the server boots fine
with just `EPICS_CA_ADDR_LIST` set; unconfigured providers report themselves
as `unconfigured` rather than erroring, and `diagnose_device()` still
returns a graceful partial report. See [.env.example](.env.example) for
every provider's config, and [docs/providers.md](docs/providers.md) for what
each one talks to.

Serve over SSE instead of stdio:

```bash
.venv/bin/python -m argus --transport sse --host 0.0.0.0 --port 8000
```

## Backward compatibility

The original 3 tools still exist, unchanged, so existing clients (including
the example scripts under `test/`) work with zero changes:

- `get_pv_value(pv_name)` → `{"status": "success", "value": ...}`
- `set_pv_value(pv_name, pv_value)` → `{"status": "success", "message": ...}`
- `get_pv_info(pv_name)` → `{"status": "success", "info": {...}}`

`get_pv`/`set_pv` are the new, richer equivalents (include timestamp and
alarm severity); the legacy names are thin aliases with byte-identical
input schemas, enforced by
`tests/tools/test_pv_tools_backward_compat.py`.

## Tools

| Tool | What it does |
|---|---|
| `get_pv` / `set_pv` / `get_pv_info` | Read/write/inspect a single PV |
| `get_pv_value` / `set_pv_value` | Legacy aliases of `get_pv`/`set_pv` |
| `search_pvs` | Search PVs/channels by name, tag, or property (ChannelFinder) |
| `get_device` | Full device metadata: PVs, IOC, pod, namespace, rack, owner, docs |
| `device_status` | Quick health snapshot: live PVs + pod status |
| `diagnose_device` | Full cross-system diagnostic report, one call |
| `beamline_status` | Aggregate status across a group of devices |
| `get_history` | Historical trend data for a PV (Archiver Appliance) |
| `get_alarm_history` | Recent alarm-tagged logbook entries for a device |
| `get_logs` | Search historical application/IOC logs (Elasticsearch) |
| `list_iocs` | List IOCs and their Kubernetes pod status |
| `restart_ioc` | Restart an IOC's pod |
| `machine_summary` | Machine-wide IOC health + recent alarm counts |
| `execute_procedure` | Run a named, pre-approved operational procedure (scaffolded; no procedures ship yet — see [ADR context](docs/adr/)) |
| `search_documentation` | Search technical documentation (local TF-IDF by default, or RAGFLOW — see [providers.md](docs/providers.md)) |

## Development

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Tests never require a running EPICS/Kubernetes/ArgoCD/etc. instance — every
backend is mocked. See [docs/developer-guide.md](docs/developer-guide.md)
for how to add a new provider or tool, and
[docs/class-diagram.md](docs/class-diagram.md) for the object model.

## EPICS Channel Access, for local testing

```bash
softIoc -d ~/EPICS/DB/test.db
caget temperature:water
caput temperature:water 100
```

then point ARGUS at it with `EPICS_CA_ADDR_LIST=127.0.0.1` in `.env`.

## Deploying

- **Docker**: `docker build -t argus .` — runs `python -m argus --transport stdio` by default; override the command for SSE.
- **Smithery**: `smithery.yaml` launches `python -m argus --transport stdio`.
