"""Device resolution: the metadata-only half of the device-centric model.

ChannelFinder is the source of truth (see docs/adr/0002). A `device` property
on CF channels groups PVs under one device name; other well-known properties
(deviceClass, iocName, rack, owner, k8sNamespace, k8sPod, argocdApp, gitRepo,
docRef) populate the rest of the Device model, all optional. If ChannelFinder
is unconfigured, resolve_device() still works for a bare PV name — it just
can't enrich it with cross-system metadata.

This service only assembles metadata; it never fetches live data (PVs, pod
status, logs) — that's diagnostics_service's job, keeping "providers
retrieve, services combine" honest even at the service-to-service boundary.
"""

from __future__ import annotations

from argus.core.cache import AsyncTTLCache
from argus.providers.channelfinder.channelfinder import ChannelFinderProvider
from argus.providers.channelfinder.exceptions import ChannelFinderError
from argus.providers.channelfinder.models import CFChannel
from argus.services.models import Device

_DEVICE_PROPERTY = "device"
_KNOWN_PROPERTIES = {
    "deviceClass": "device_class",
    "iocName": "ioc_name",
    "rack": "rack",
    "owner": "owner",
    "k8sNamespace": "namespace",
    "k8sPod": "pod_name",
    "argocdApp": "argocd_app",
    "gitRepo": "git_repo",
    "docRef": "documentation_refs",
    "networkLocation": "network_location",
}


class DeviceService:
    def __init__(self, channelfinder: ChannelFinderProvider, cache: AsyncTTLCache) -> None:
        self._channelfinder = channelfinder
        self._cache = cache

    async def resolve_device(self, name: str) -> Device:
        return await self._cache.get_or_set(f"device:{name}", lambda: self._resolve_device_uncached(name))

    async def _resolve_device_uncached(self, name: str) -> Device:
        if not self._channelfinder.is_configured():
            return Device(name=name, pv_names=[name], primary_pv=name)

        try:
            channels = await self._channelfinder.find_channels(**{_DEVICE_PROPERTY: name})
        except ChannelFinderError:
            channels = []

        if not channels:
            # Fall back to treating the bare name as a single PV — still
            # useful for get_pv/diagnose_device against ungrouped channels.
            try:
                channel = await self._channelfinder.get_channel(name)
            except ChannelFinderError:
                channel = None
            channels = [channel] if channel else []

        if not channels:
            return Device(name=name, pv_names=[name], primary_pv=name)

        return _build_device(name, channels)

    async def search_devices(self, query: str, limit: int = 50) -> list[Device]:
        if not self._channelfinder.is_configured():
            return []
        try:
            channels = await self._channelfinder.find_channels(query)
        except ChannelFinderError:
            return []

        by_device: dict[str, list[CFChannel]] = {}
        for channel in channels[:limit]:
            device_name = channel.properties.get(_DEVICE_PROPERTY, channel.name)
            by_device.setdefault(device_name, []).append(channel)

        return [_build_device(name, chans) for name, chans in by_device.items()]


def _build_device(name: str, channels: list[CFChannel]) -> Device:
    pv_names = [c.name for c in channels]
    merged_properties: dict[str, str] = {}
    tags: set[str] = set()
    owner: str | None = None
    for channel in channels:
        merged_properties.update(channel.properties)
        tags.update(channel.tags)
        owner = owner or channel.owner

    device = Device(
        name=name,
        pv_names=pv_names,
        primary_pv=pv_names[0] if pv_names else None,
        owner=owner,
        tags=sorted(tags),
        properties=merged_properties,
    )
    for cf_key, field_name in _KNOWN_PROPERTIES.items():
        value = merged_properties.get(cf_key)
        if value is None:
            continue
        if field_name == "documentation_refs":
            device.documentation_refs = [value]
        else:
            setattr(device, field_name, value)
    return device
