"""Archiver Appliance provider.

Talks to the well-known REST retrieval API
(``/retrieval/data/getData.json``) exposed by EPICS Archiver Appliance
deployments. No official Python client exists, so this is a thin httpx
wrapper — the same approach every EPICS site's own scripts use.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import httpx

from argus.config.settings import ArchiverSettings
from argus.providers.archiver.exceptions import (
    ArchiverQueryError,
    ArchiverTimeoutError,
    ArchiverUnavailableError,
    ArchiverUnconfiguredError,
)
from argus.providers.archiver.models import ArchiverSample, ArchiverSeries
from argus.providers.base import ProviderHealth, ProviderStatus


class ArchiverApplianceProvider:
    name: ClassVar[str] = "archiver"

    def __init__(self, settings: ArchiverSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.base_url)

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{self._settings.base_url}/retrieval/bpl/getVersion")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise ArchiverUnconfiguredError("Archiver Appliance is not configured (set ARCHIVER_BASE_URL).")

    async def get_data(
        self, pv_name: str, start: datetime, end: datetime, *, operator: str | None = None, timeout: float = 8.0
    ) -> ArchiverSeries:
        self._require_configured()
        pv_query = f"{operator}({pv_name})" if operator else pv_name
        params = {"pv": pv_query, "from": _iso(start), "to": _iso(end)}
        url = f"{self._settings.base_url}/retrieval/data/getData.json"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ArchiverTimeoutError(f"Timeout retrieving archiver data for '{pv_name}'") from exc
        except httpx.HTTPError as exc:
            raise ArchiverUnavailableError(f"Archiver Appliance unreachable: {exc}") from exc

        try:
            series = payload[0]
            samples = [
                ArchiverSample(
                    timestamp=datetime.fromtimestamp(point["secs"] + point.get("nanos", 0) / 1e9),
                    value=point["val"],
                    severity=point.get("severity"),
                )
                for point in series.get("data", [])
            ]
        except (KeyError, IndexError, TypeError) as exc:
            raise ArchiverQueryError(f"Unexpected Archiver Appliance response shape for '{pv_name}': {exc}") from exc

        return ArchiverSeries(pv_name=pv_name, samples=samples)

    async def get_latest(self, pv_name: str, *, timeout: float = 5.0) -> ArchiverSample | None:
        now = datetime.utcnow()
        series = await self.get_data(pv_name, now.replace(hour=0, minute=0, second=0), now, timeout=timeout)
        return series.samples[-1] if series.samples else None


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")
