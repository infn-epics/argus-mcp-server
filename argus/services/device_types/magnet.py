"""devgroup "mag": power supplies for quadrupoles, correctors, dipoles, etc."""

from __future__ import annotations

from argus.services.device_types.base import DeviceTypeProfile, DevfuncRule

MAGNET = DeviceTypeProfile(
    devgroup="mag",
    devfunc_rules=(
        DevfuncRule(("HCV", "HCOR", "VCOR", "HCR", "VCR", "CHH", "CVV"), "COR"),
        DevfuncRule(("QUA", "QUAD", "QSK"), "QUA"),
        DevfuncRule(("DIP", "DPL", "DHS", "DHR", "DHP"), "DIP"),
        DevfuncRule(("SOL",), "SOL"),
        DevfuncRule(("SEX",), "SEX"),
        DevfuncRule(("UFS",), "UFS"),
    ),
    key_pv_suffixes={
        "current_setpoint": "CURRENT_SP",
        "current_readback": "CURRENT_RB",
        "state_setpoint": "STATE_SP",
        "state_readback": "STATE_RB",
    },
)
