"""ChannelFinder provider — the standard EPICS device/PV metadata registry.

This is the source of truth device_service uses to resolve a device name into
its PVs, IOC, namespace, rack, owner etc. (via CF properties/tags on channels).
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from argus.config.settings import ChannelFinderSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.channelfinder.exceptions import (
    ChannelFinderQueryError,
    ChannelFinderTimeoutError,
    ChannelFinderUnavailableError,
    ChannelFinderUnconfiguredError,
)
from argus.providers.channelfinder.models import CFChannel


class ChannelFinderProvider:
    name: ClassVar[str] = "channelfinder"

    def __init__(self, settings: ChannelFinderSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.base_url)

    def _auth(self) -> tuple[str, str] | None:
        if self._settings.username and self._settings.password:
            return (self._settings.username, self._settings.password)
        return None

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3, auth=self._auth()) as client:
                resp = await client.get(f"{self._settings.base_url}/ChannelFinder/resources/channels/count")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise ChannelFinderUnconfiguredError(
                "ChannelFinder is not configured (set CHANNELFINDER_BASE_URL)."
            )

    async def find_channels(
        self, query: str | None = None, *, timeout: float = 5.0, **tags_and_properties: str
    ) -> list[CFChannel]:
        self._require_configured()
        params: dict[str, str] = {}
        if query:
            params["~name"] = query
        params.update(tags_and_properties)

        url = f"{self._settings.base_url}/ChannelFinder/resources/channels"
        try:
            async with httpx.AsyncClient(timeout=timeout, auth=self._auth()) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ChannelFinderTimeoutError(f"Timeout querying ChannelFinder for '{query}'") from exc
        except httpx.HTTPError as exc:
            raise ChannelFinderUnavailableError(f"ChannelFinder unreachable: {exc}") from exc

        try:
            return [_to_channel(entry) for entry in payload]
        except (KeyError, TypeError) as exc:
            raise ChannelFinderQueryError(f"Unexpected ChannelFinder response shape: {exc}") from exc

    async def get_channel(self, name: str, *, timeout: float = 5.0) -> CFChannel | None:
        self._require_configured()
        url = f"{self._settings.base_url}/ChannelFinder/resources/channels/{name}"
        try:
            async with httpx.AsyncClient(timeout=timeout, auth=self._auth()) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ChannelFinderTimeoutError(f"Timeout fetching channel '{name}' from ChannelFinder") from exc
        except httpx.HTTPError as exc:
            raise ChannelFinderUnavailableError(f"ChannelFinder unreachable: {exc}") from exc

        return _to_channel(payload)


def _to_channel(entry: dict) -> CFChannel:
    return CFChannel(
        name=entry["name"],
        owner=entry.get("owner"),
        properties={p["name"]: p.get("value") for p in entry.get("properties", [])},
        tags=[t["name"] for t in entry.get("tags", [])],
    )
