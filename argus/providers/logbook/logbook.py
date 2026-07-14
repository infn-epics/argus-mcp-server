"""Electronic logbook provider, against an olog-compatible REST API.

Olog/phoebus-olog is the de facto standard EPICS-world electronic logbook
(used at SNS, ESS, BNL, etc.); this client is generic enough to also work
against olog-API-compatible forks.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import httpx

from argus.config.settings import LogbookSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.logbook.exceptions import (
    LogbookQueryError,
    LogbookTimeoutError,
    LogbookUnavailableError,
    LogbookUnconfiguredError,
)
from argus.providers.logbook.models import LogbookEntry


class LogbookProvider:
    name: ClassVar[str] = "logbook"

    def __init__(self, settings: LogbookSettings) -> None:
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
                resp = await client.get(f"{self._settings.base_url}/Olog/logbooks")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise LogbookUnconfiguredError("Logbook is not configured (set LOGBOOK_BASE_URL).")

    async def search_entries(
        self,
        *,
        logbook: str | None = None,
        tags: list[str] | None = None,
        text: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
        timeout: float = 5.0,
    ) -> list[LogbookEntry]:
        self._require_configured()
        params: dict[str, str] = {"limit": str(limit)}
        if logbook:
            params["logbooks"] = logbook
        if tags:
            params["tags"] = ",".join(tags)
        if text:
            params["search"] = text
        if since:
            params["start"] = since.isoformat()

        url = f"{self._settings.base_url}/Olog/logs"
        try:
            async with httpx.AsyncClient(timeout=timeout, auth=self._auth()) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise LogbookTimeoutError("Timeout searching logbook entries") from exc
        except httpx.HTTPError as exc:
            raise LogbookUnavailableError(f"Logbook unreachable: {exc}") from exc

        try:
            return [_to_entry(item) for item in payload]
        except (KeyError, TypeError) as exc:
            raise LogbookQueryError(f"Unexpected logbook response shape: {exc}") from exc

    async def create_entry(
        self, title: str, text: str, logbooks: list[str], tags: list[str] | None = None, *, timeout: float = 5.0
    ) -> LogbookEntry:
        self._require_configured()
        body = {
            "title": title,
            "description": text,
            "logbooks": [{"name": lb} for lb in logbooks],
            "tags": [{"name": t} for t in (tags or [])],
        }
        url = f"{self._settings.base_url}/Olog/logs"
        try:
            async with httpx.AsyncClient(timeout=timeout, auth=self._auth()) as client:
                resp = await client.put(url, json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise LogbookTimeoutError("Timeout creating logbook entry") from exc
        except httpx.HTTPError as exc:
            raise LogbookUnavailableError(f"Logbook unreachable: {exc}") from exc

        return _to_entry(payload)


def _to_entry(payload: dict) -> LogbookEntry:
    created = payload.get("createdDate")
    return LogbookEntry(
        id=str(payload.get("id", "")),
        title=payload.get("title", ""),
        text=payload.get("description", ""),
        logbooks=[lb.get("name") for lb in payload.get("logbooks", [])],
        tags=[t.get("name") for t in payload.get("tags", [])],
        created_at=datetime.fromtimestamp(created / 1000) if isinstance(created, (int, float)) else None,
        author=payload.get("owner"),
    )
