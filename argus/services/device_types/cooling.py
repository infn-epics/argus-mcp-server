"""devgroup "cool": cooling circuits. Not seen yet in BTF's own deploy YAML,
but part of the same PV-suffix convention family as magnet.py/vacuum.py
(epik8s-btf/opi/epik8s-opi/Scripts/epik8sutil.py's pvset/pvrb) -- included
for consistency so a beamline using it needs no ARGUS code change.
"""

from __future__ import annotations

from argus.services.device_types.base import DeviceTypeProfile

COOLING = DeviceTypeProfile(
    devgroup="cool",
    key_pv_suffixes={
        "temp_setpoint": "TEMP_SP",
        "temp_readback": "TEMP_RB",
        "state_setpoint": "STATE_SP",
        "state_readback": "STATE_RB",
    },
)
