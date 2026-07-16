"""Phoebus save-and-restore provider — read-only.

Talks to the REST API exposed by the Phoebus save-and-restore service
(deployed in epik8s beamlines via phoebus-services-chart, image
ghcr.io/infn-epics/phoebus/service-save-and-restore). Endpoints below were
confirmed live against a real BTF deployment, not assumed from docs:

    GET /search?...          -> {"hitCount": N, "nodes": [Node, ...]}
    GET /node/{id}           -> Node
    GET /node/{id}/children  -> [Node, ...]
    GET /config/{id}         -> {"uniqueId": ..., "pvList": [...]}
    GET /snapshot/{id}       -> {"uniqueId": ..., "snapshotItems": [...]}

Read-only by design: /restore/* on the real service returns 401 without an
OAuth2 bearer token (the save-and-restore service's own login), which ARGUS
has no credentials for yet. Applying a snapshot writes potentially dozens of
PVs across the machine back to old values -- the highest-blast-radius write
ARGUS could have, so it's deliberately left out of this first version rather
than guessed at. See docs/adr/ if a future ADR formalizes restore support.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import httpx

from argus.config.settings import SaveRestoreSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.saverestore.exceptions import (
    SaveRestoreQueryError,
    SaveRestoreTimeoutError,
    SaveRestoreUnavailableError,
    SaveRestoreUnconfiguredError,
)
from argus.providers.saverestore.models import SnrConfiguration, SnrNode, SnrPvEntry, SnrSnapshot, SnrSnapshotValue


class SaveRestoreProvider:
    name: ClassVar[str] = "saverestore"

    def __init__(self, settings: SaveRestoreSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.base_url)

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self._settings.base_url}/")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise SaveRestoreUnconfiguredError("Save-and-restore is not configured (set SAVERESTORE_BASE_URL).")

    async def _get(self, path: str, *, params: dict | None = None, timeout: float) -> dict | list:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{self._settings.base_url}{path}", params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise SaveRestoreTimeoutError(f"Timeout calling save-and-restore {path}") from exc
        except httpx.HTTPError as exc:
            raise SaveRestoreUnavailableError(f"Save-and-restore unreachable: {exc}") from exc

    async def search(self, query: str, *, timeout: float = 5.0) -> list[SnrNode]:
        self._require_configured()
        payload = await self._get("/search", params={"query": query}, timeout=timeout)
        try:
            return [_to_node(n) for n in payload["nodes"]]
        except (KeyError, TypeError) as exc:
            raise SaveRestoreQueryError(f"Unexpected save-and-restore search response shape: {exc}") from exc

    async def get_node(self, node_id: str, *, timeout: float = 5.0) -> SnrNode:
        self._require_configured()
        payload = await self._get(f"/node/{node_id}", timeout=timeout)
        try:
            return _to_node(payload)
        except (KeyError, TypeError) as exc:
            raise SaveRestoreQueryError(f"Unexpected save-and-restore node response shape: {exc}") from exc

    async def get_children(self, node_id: str, *, timeout: float = 5.0) -> list[SnrNode]:
        self._require_configured()
        payload = await self._get(f"/node/{node_id}/children", timeout=timeout)
        try:
            return [_to_node(n) for n in payload]
        except (KeyError, TypeError) as exc:
            raise SaveRestoreQueryError(f"Unexpected save-and-restore children response shape: {exc}") from exc

    async def get_configuration(self, config_id: str, *, timeout: float = 5.0) -> SnrConfiguration:
        self._require_configured()
        payload = await self._get(f"/config/{config_id}", timeout=timeout)
        try:
            pv_list = [
                SnrPvEntry(
                    pv_name=pv["pvName"],
                    readback_pv_name=pv.get("readbackPvName"),
                    read_only=bool(pv.get("readOnly", False)),
                )
                for pv in payload["pvList"]
            ]
            return SnrConfiguration(unique_id=payload["uniqueId"], pv_list=pv_list)
        except (KeyError, TypeError) as exc:
            raise SaveRestoreQueryError(f"Unexpected save-and-restore config response shape: {exc}") from exc

    async def get_snapshot(self, snapshot_id: str, *, timeout: float = 5.0) -> SnrSnapshot:
        self._require_configured()
        payload = await self._get(f"/snapshot/{snapshot_id}", timeout=timeout)
        try:
            items = [_to_snapshot_value(item) for item in payload["snapshotItems"]]
            return SnrSnapshot(unique_id=payload["uniqueId"], items=items)
        except (KeyError, TypeError) as exc:
            raise SaveRestoreQueryError(f"Unexpected save-and-restore snapshot response shape: {exc}") from exc


def _to_node(payload: dict) -> SnrNode:
    return SnrNode(
        unique_id=payload["uniqueId"],
        name=payload["name"],
        node_type=payload["nodeType"],
        description=payload.get("description"),
        created=_epoch_ms_to_dt(payload.get("created")),
        last_modified=_epoch_ms_to_dt(payload.get("lastModified")),
        user_name=payload.get("userName"),
    )


def _to_snapshot_value(item: dict) -> SnrSnapshotValue:
    config_pv = item.get("configPv", {})
    value_field = item.get("value") or {}
    return SnrSnapshotValue(
        pv_name=config_pv.get("pvName", ""),
        value=value_field.get("value"),
        readback_value=(item.get("readbackValue") or {}).get("value"),
        units=(value_field.get("display") or {}).get("units"),
        severity=(value_field.get("alarm") or {}).get("severity"),
    )


def _epoch_ms_to_dt(value: object) -> datetime | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value / 1000)
