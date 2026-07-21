"""Structured beamline device inventory, parsed from an epik8s-style deploy
YAML (with iocDefaults template inheritance resolved). Read-only, same as
knowledge_tools.py — this just adds parsing/classification on top of
KnowledgeService.get_file().
"""

from __future__ import annotations

import dataclasses
from typing import Any

from argus.core.context import AppContext
from argus.core.errors import ValidationError
from argus.mcp_server.tools.registry import ToolDefinition
from argus.services.beamline_inventory_service import DEFAULT_INVENTORY_PATH

_REPO_URL_DESC = (
    "Optional - defaults to this beamline's own configured repo (GIT_DEFAULT_REPOS) when omitted, "
    "which is correct for almost every call. Only pass this to look at a *different* beamline's repo "
    "instead - do not guess a URL from this beamline's name (repo naming isn't consistent, e.g. "
    "epik8s-btf.git but epik8-sparc.git). A git URL, e.g. https://github.com/infn-epics/ioc-chart.git "
    "or https://baltig.infn.it/lnf-da-control/epik8s-btf.git."
)

_LIST_DEVICES_SCHEMA = {
    "type": "object",
    "properties": {
        "repo": {"type": "string", "description": _REPO_URL_DESC},
        "path": {
            "type": "string",
            "description": f"Path to the beamline's epik8s-style deploy YAML. Defaults to '{DEFAULT_INVENTORY_PATH}'.",
        },
        "ref": {
            "type": "string",
            "description": (
                "Git ref to read. Defaults to 'HEAD', which resolves to whatever branch this beamline is "
                "actually deployed from (GIT_DEFAULT_REF) — not necessarily the repo's default branch. "
                "Only pass this to look at a *different* ref (a specific tag/commit, or another branch)."
            ),
        },
        "devgroup": {
            "type": "string",
            "description": "Filter by device group, e.g. 'mag' (magnets), 'vac' (vacuum), 'mot' (motors), 'cam' (cameras), 'diag' (diagnostics).",
        },
        "devfunc": {
            "type": "string",
            "description": (
                "Filter by device function within a group. Within 'mag': 'QUA' (quadrupole), 'COR' "
                "(corrector), 'DIP' (dipole), 'SOL' (solenoid), 'SEX' (sextupole), 'UFS'. Within 'mot': "
                "'SLT' (slit), 'FLG' (flag), 'MIR' (mirror), 'HMOT'/'VMOT' (horiz/vert motor), or 'MOT' "
                "(generic). Within 'vac': 'ion' (ion pump)."
            ),
        },
        "zone": {"type": "string", "description": "Filter by zone, e.g. 'BTF1', 'BTF2', 'LINAC'."},
    },
    "required": [],
}


async def _list_beamline_devices(arguments: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    repo = arguments.get("repo")
    if repo is not None and not isinstance(repo, str):
        raise ValidationError("repo must be a string.")

    devices = await ctx.beamline_inventory_service.list_devices(
        repo,
        path=arguments.get("path", DEFAULT_INVENTORY_PATH),
        ref=arguments.get("ref", "HEAD"),
        devgroup=arguments.get("devgroup"),
        devfunc=arguments.get("devfunc"),
        zone=arguments.get("zone"),
    )
    return {"device_count": len(devices), "devices": [dataclasses.asdict(d) for d in devices]}


TOOLS = [
    ToolDefinition(
        name="list_beamline_devices",
        description=(
            "THE DEFAULT, FIRST TOOL for any question involving IOCs, devices, device names, device "
            "types, zones, or device groups (magnets/mag, vacuum/vac, motors/mot, cameras/cam, "
            "diagnostics/diag) — e.g. 'what magnets/quadrupoles/vacuum devices exist on this beamline or "
            "zone'. This is the main source of information: it is on the YAML, not in PV search. Do not "
            "call search_pvs or beamline_status first and do not retry them repeatedly hoping for a "
            "different result — if the question is about what exists rather than a live PV value, call "
            "this tool first, once. repo is optional and defaults to THIS beamline's own configured repo "
            "— call with no repo argument for 'this beamline's own devices', which is almost always what's "
            "wanted; never guess a repo URL from the beamline's name, only pass repo explicitly to look at "
            "a *different* beamline's inventory. Returns the beamline's device inventory parsed from its "
            "epik8s-style deploy YAML, with iocDefaults template values already merged in — many IOCs only declare a "
            "'template' and inherit devgroup/devtype from iocDefaults[template] rather than setting it "
            "directly, so reading the raw file yourself and grep-ing for devgroup will undercount. Each "
            "device also gets a devfunc classification within its devgroup (e.g. QUA/COR/DIP/SOL within "
            "'mag') derived the same way the control-room OPI console does it. Each device also includes "
            "key_pvs: a role -> exact PV name map for that device type's important setpoint/readback PVs "
            "(e.g. a 'mag' device's key_pvs has current_setpoint/current_readback/state_setpoint/"
            "state_readback) — for 'what's the current/status of this power supply' questions, read the "
            "PV name straight from key_pvs and call get_pv/get_pv_value on it directly; do not guess or "
            "search for the PV name. key_pvs is empty for device types with no registered convention yet. "
            "Filter with devgroup/devfunc/zone, or omit them to list everything. For raw file content, "
            "history, or metadata this doesn't model (asset links, IOC-level params, template names), use "
            "get_config_history instead."
        ),
        input_schema=_LIST_DEVICES_SCHEMA,
        handler=_list_beamline_devices,
    ),
]
