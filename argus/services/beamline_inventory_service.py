"""Structured device inventory parsed from an epik8s-style beamline deploy YAML.

epik8s beamline repos (e.g. epik8s-btf's deploy/values.yaml) declare devices
under `epicsConfiguration.iocs`, classified by `devgroup` (mag/vac/mot/cam/
diag/...) and `devtype`. Critically, many IOC entries don't set `devgroup`/
`devtype` directly — they inherit them from `iocDefaults[template]`, keyed by
the IOC's own `template` (or `devtype` as a fallback key). Reading the raw
YAML text without applying this merge undercounts devices, since
template-inherited classification is invisible without it.

This mirrors the merge-then-classify logic already used by the Phoebus OPI
console's own config loader (epik8s-btf/opi/epik8s-opi/Scripts/epik8sutil.py:
_merge_ioc_defaults + the devgroup/devfunc rules in conf_to_dev), so ARGUS
and the control-room OPIs agree on what counts as e.g. a quadrupole.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from argus.core.errors import ArgusError
from argus.services.knowledge_service import KnowledgeService

DEFAULT_INVENTORY_PATH = "deploy/values.yaml"

# devgroup == "mag" name substrings -> devfunc, checked in this order.
_MAG_DEVFUNC_RULES: list[tuple[tuple[str, ...], str]] = [
    (("HCV", "HCOR", "VCOR", "HCR", "VCR", "CHH", "CVV"), "COR"),
    (("QUA", "QUAD", "QSK"), "QUA"),
    (("DIP", "DPL", "DHS", "DHR", "DHP"), "DIP"),
    (("SOL",), "SOL"),
    (("SEX",), "SEX"),
    (("UFS",), "UFS"),
]

# devgroup == "mot" name/iocprefix substrings -> devfunc. "MOT" is the
# fallback devfunc for any mot-group device that matches none of these.
_MOT_DEVFUNC_RULES: list[tuple[tuple[str, ...], str]] = [
    (("SLT",), "SLT"),
    (("FLG",), "FLG"),
    (("MIR",), "MIR"),
    (("HMOT",), "HMOT"),
    (("VMOT",), "VMOT"),
]


class BeamlineInventoryError(ArgusError):
    code = "beamline_inventory_error"


@dataclass
class BeamlineDevice:
    name: str
    ioc_name: str
    iocprefix: str | None
    devgroup: str | None
    devtype: str | None
    devfunc: str | None
    zones: list[str]
    geo: float | None = None
    asset: str | None = None
    opi: str | None = None
    template: str | None = None


def _merge_ioc_defaults(ioc_defaults: dict, ioc: dict) -> dict:
    template = ioc.get("template") or ioc.get("devtype") or ""
    defaults = ioc_defaults.get(template) if template else None
    if not defaults:
        return ioc
    merged = dict(defaults)
    merged.update(ioc)
    return merged


def _normalize_zones(value: object) -> list[str]:
    if value is None:
        return ["ALL"]
    if isinstance(value, str):
        return [value]
    return [str(z) for z in value]


def _device_zones(ioc: dict, dev: dict) -> list[str]:
    ioc_zone_raw = ioc.get("zones", "ALL")
    if "zones" in dev:
        zones = _normalize_zones(dev["zones"])
        if isinstance(ioc_zone_raw, str) and ioc_zone_raw != "ALL" and ioc_zone_raw not in zones:
            zones.append(ioc_zone_raw)
        return zones
    return _normalize_zones(ioc_zone_raw)


def _derive_devfunc(devgroup: str | None, name: str, iocprefix: str) -> str | None:
    if devgroup == "mag":
        for substrings, devfunc in _MAG_DEVFUNC_RULES:
            if any(s in name for s in substrings):
                return devfunc
        return None
    if devgroup == "mot":
        for substrings, devfunc in _MOT_DEVFUNC_RULES:
            if any(s in name or s in iocprefix for s in substrings):
                return devfunc
        return "MOT"
    if devgroup == "vac" and "SIP" in name:
        return "ion"
    return None


class BeamlineInventoryService:
    def __init__(self, knowledge: KnowledgeService) -> None:
        self._knowledge = knowledge

    async def list_devices(
        self,
        repo: str,
        path: str = DEFAULT_INVENTORY_PATH,
        ref: str = "HEAD",
        devgroup: str | None = None,
        devfunc: str | None = None,
        zone: str | None = None,
    ) -> list[BeamlineDevice]:
        file = await self._knowledge.get_file(repo, path, ref)
        try:
            data = yaml.safe_load(file.content) or {}
        except yaml.YAMLError as exc:
            raise BeamlineInventoryError(f"Could not parse '{path}' as YAML: {exc}") from exc

        ioc_defaults = data.get("iocDefaults") or {}
        iocs = ((data.get("epicsConfiguration") or {}).get("iocs")) or []

        devices: list[BeamlineDevice] = []
        for raw_ioc in iocs:
            ioc = _merge_ioc_defaults(ioc_defaults, raw_ioc)
            ioc_name = ioc.get("name", "")
            iocprefix = ioc.get("iocprefix", "")
            ioc_devgroup = ioc.get("devgroup")
            ioc_devtype = ioc.get("devtype")
            ioc_asset = ioc.get("asset")
            ioc_opi = ioc.get("opi")
            template = ioc.get("template")

            for dev in ioc.get("devices", []):
                name = dev.get("alias") or dev.get("name")
                if not name:
                    continue
                dev_devtype = dev.get("devtype", ioc_devtype)
                dev_devfunc = dev.get("devfunc") or _derive_devfunc(ioc_devgroup, name, iocprefix)

                device = BeamlineDevice(
                    name=name,
                    ioc_name=ioc_name,
                    iocprefix=iocprefix or None,
                    devgroup=ioc_devgroup,
                    devtype=dev_devtype,
                    devfunc=dev_devfunc,
                    zones=_device_zones(ioc, dev),
                    geo=dev.get("geo"),
                    asset=dev.get("asset", ioc_asset),
                    opi=dev.get("opi", ioc_opi),
                    template=template,
                )

                if devgroup and device.devgroup != devgroup:
                    continue
                if devfunc and device.devfunc != devfunc:
                    continue
                if zone and zone not in device.zones and "ALL" not in device.zones:
                    continue
                devices.append(device)

        return devices
