"""devgroup "mot": motorized elements (slits, flags, mirrors, generic motors).

key_pv_suffixes is intentionally empty -- BTF's motor PV naming convention
for position setpoint/readback hasn't been confirmed yet. Add it here once
known; nothing else needs to change.
"""

from __future__ import annotations

from argus.services.device_types.base import DeviceTypeProfile, DevfuncRule

MOTOR = DeviceTypeProfile(
    devgroup="mot",
    devfunc_rules=(
        DevfuncRule(("SLT",), "SLT"),
        DevfuncRule(("FLG",), "FLG"),
        DevfuncRule(("MIR",), "MIR", check_iocprefix=True),
        DevfuncRule(("HMOT",), "HMOT"),
        DevfuncRule(("VMOT",), "VMOT"),
    ),
    devfunc_fallback="MOT",
)
