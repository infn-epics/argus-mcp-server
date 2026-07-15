"""Registry of per-device-type profiles, keyed by devgroup code."""

from __future__ import annotations

from argus.services.device_types.base import DeviceTypeProfile, DevfuncRule
from argus.services.device_types.cooling import COOLING
from argus.services.device_types.magnet import MAGNET
from argus.services.device_types.motor import MOTOR
from argus.services.device_types.vacuum import VACUUM

_REGISTRY: dict[str, DeviceTypeProfile] = {profile.devgroup: profile for profile in (MAGNET, VACUUM, MOTOR, COOLING)}

__all__ = ["DeviceTypeProfile", "DevfuncRule", "get_profile"]


def get_profile(devgroup: str | None) -> DeviceTypeProfile | None:
    """Look up a device type's profile by devgroup (mag/vac/mot/cool/...).

    Returns None for devgroups with no registered profile (e.g. cam, diag) --
    callers should treat that as "no extra classification/key PVs available
    yet", not an error.
    """
    return _REGISTRY.get(devgroup) if devgroup else None
