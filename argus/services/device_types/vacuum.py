"""devgroup "vac": vacuum gauges/pumps."""

from __future__ import annotations

from argus.services.device_types.base import DeviceTypeProfile, DevfuncRule

VACUUM = DeviceTypeProfile(
    devgroup="vac",
    devfunc_rules=(DevfuncRule(("SIP",), "ion"),),
    key_pv_suffixes={
        "pressure_readback": "PRES_RB",
    },
)
