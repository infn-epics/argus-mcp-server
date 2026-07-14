"""ArgoCD provider — REST client against the ArgoCD API server.

Used by diagnostics to map an IOC/device to its GitOps application state and
the backing git repository.
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from argus.config.settings import ArgoCDSettings
from argus.providers.argocd.exceptions import (
    ArgoCDAuthError,
    ArgoCDTimeoutError,
    ArgoCDUnavailableError,
    ArgoCDUnconfiguredError,
)
from argus.providers.argocd.models import ArgoApplicationStatus
from argus.providers.base import ProviderHealth, ProviderStatus


class ArgoCDProvider:
    name: ClassVar[str] = "argocd"

    def __init__(self, settings: ArgoCDSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.server_url)

    def _headers(self) -> dict[str, str]:
        if self._settings.auth_token:
            return {"Authorization": f"Bearer {self._settings.auth_token}"}
        return {}

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3, headers=self._headers()) as client:
                resp = await client.get(f"{self._settings.server_url}/api/v1/session/userinfo")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise ArgoCDUnconfiguredError("ArgoCD is not configured (set ARGOCD_SERVER_URL).")

    async def get_application(self, app_name: str, *, timeout: float = 5.0) -> ArgoApplicationStatus | None:
        self._require_configured()
        url = f"{self._settings.server_url}/api/v1/applications/{app_name}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    return None
                if resp.status_code in (401, 403):
                    raise ArgoCDAuthError(f"ArgoCD rejected credentials for application '{app_name}'")
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ArgoCDTimeoutError(f"Timeout fetching ArgoCD application '{app_name}'") from exc
        except httpx.HTTPError as exc:
            raise ArgoCDUnavailableError(f"ArgoCD unreachable: {exc}") from exc

        return _to_status(payload)

    async def list_applications(self, project: str | None = None, *, timeout: float = 5.0) -> list[ArgoApplicationStatus]:
        self._require_configured()
        params = {"project": project} if project else {}
        url = f"{self._settings.server_url}/api/v1/applications"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise ArgoCDTimeoutError("Timeout listing ArgoCD applications") from exc
        except httpx.HTTPError as exc:
            raise ArgoCDUnavailableError(f"ArgoCD unreachable: {exc}") from exc

        return [_to_status(item) for item in payload.get("items", [])]


def _to_status(payload: dict) -> ArgoApplicationStatus:
    status = payload.get("status", {})
    sync = status.get("sync", {})
    health = status.get("health", {})
    return ArgoApplicationStatus(
        name=payload.get("metadata", {}).get("name", ""),
        sync_status=sync.get("status", "Unknown"),
        health_status=health.get("status", "Unknown"),
        revision=sync.get("revision"),
        repo_url=payload.get("spec", {}).get("source", {}).get("repoURL"),
        last_sync_at=status.get("operationState", {}).get("finishedAt"),
    )
