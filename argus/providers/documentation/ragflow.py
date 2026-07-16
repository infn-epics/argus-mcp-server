"""RAGFLOW-backed DocumentationProvider.

Talks to RAGFLOW's own REST retrieval API (POST /api/v1/retrieval) directly
— not through RAGFLOW's separate MCP bridge server — so it gets the exact
same server-to-server auth/error/logging treatment every other ARGUS
provider already has, and sidesteps whatever SSRF/gateway policy a
client-side MCP connection (e.g. from LibreChat) might sit behind.

Implements the same DocumentationProvider protocol as
LocalTfidfDocumentationProvider (interface.py) — swappable via
Settings.documentation_backend with no changes to documentation_service.py
or the search_documentation tool, exactly as ADR 0003 anticipated.

RAGFLOW's REST API returns HTTP 200 even for application-level errors, e.g.
{"code": 102, "message": "`dataset_ids` is required."} -- there is no "data"
key in that case, confirmed live against a real deployment. Every call here
checks "code" before assuming "data" is present, rather than relying on
resp.raise_for_status() (which never fires for these).
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from argus.config.settings import RagflowSettings
from argus.core.cache import AsyncTTLCache
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.documentation.exceptions import (
    DocumentationQueryError,
    DocumentationTimeoutError,
    DocumentationUnavailableError,
    DocumentationUnconfiguredError,
)
from argus.providers.documentation.models import DocSearchResult


class RagflowDocumentationProvider:
    name: ClassVar[str] = "ragflow"

    def __init__(self, settings: RagflowSettings) -> None:
        self._settings = settings
        # Caches the dataset name->id listing, not any query result -- avoids
        # a GET /api/v1/datasets round trip on every search when
        # dataset_names is configured.
        self._dataset_cache: AsyncTTLCache = AsyncTTLCache(maxsize=1, ttl=300.0)

    def is_configured(self) -> bool:
        return bool(self._settings.base_url and self._settings.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._settings.api_key}"}

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3, headers=self._headers()) as client:
                resp = await client.get(f"{self._settings.base_url}/api/v1/datasets")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise DocumentationUnconfiguredError(
                "RAGFLOW is not configured (set RAGFLOW_BASE_URL and RAGFLOW_API_KEY)."
            )

    def reindex(self) -> None:
        # RAGFLOW manages its own ingestion/indexing; nothing for ARGUS to do.
        pass

    async def _post_json(self, path: str, body: dict, *, timeout: float) -> dict:
        url = f"{self._settings.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise DocumentationTimeoutError(f"Timeout calling RAGFLOW {path}") from exc
        except httpx.HTTPError as exc:
            raise DocumentationUnavailableError(f"RAGFLOW unreachable: {exc}") from exc

    async def _get_json(self, path: str, *, timeout: float) -> dict:
        url = f"{self._settings.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise DocumentationTimeoutError(f"Timeout calling RAGFLOW {path}") from exc
        except httpx.HTTPError as exc:
            raise DocumentationUnavailableError(f"RAGFLOW unreachable: {exc}") from exc

    async def _list_datasets(self, timeout: float) -> list[dict]:
        payload = await self._get_json("/api/v1/datasets", timeout=timeout)
        if payload.get("code", 0) != 0:
            raise DocumentationQueryError(f"RAGFLOW error listing datasets: {payload.get('message', 'unknown error')}")
        return payload.get("data") or []

    async def _resolve_dataset_ids(self, timeout: float) -> list[str]:
        ids: list[str] = []
        if self._settings.dataset_ids:
            ids.extend(d.strip() for d in self._settings.dataset_ids.split(",") if d.strip())

        if self._settings.dataset_names:
            wanted = [n.strip().lower() for n in self._settings.dataset_names.split(",") if n.strip()]
            datasets = await self._dataset_cache.get_or_set("datasets", lambda: self._list_datasets(timeout))
            for name in wanted:
                match = next((d for d in datasets if name in d.get("name", "").lower()), None)
                if match:
                    ids.append(match["id"])
        return ids

    async def search(self, query: str, top_k: int = 5, *, timeout: float | None = None) -> list[DocSearchResult]:
        self._require_configured()
        timeout = timeout if timeout is not None else self._settings.timeout_seconds

        body: dict = {"question": query, "page_size": top_k}
        dataset_ids = await self._resolve_dataset_ids(timeout)
        if dataset_ids:
            body["dataset_ids"] = dataset_ids

        payload = await self._post_json("/api/v1/retrieval", body, timeout=timeout)

        if payload.get("code", 0) != 0:
            raise DocumentationQueryError(f"RAGFLOW error: {payload.get('message', 'unknown error')}")

        try:
            chunks = payload["data"]["chunks"]
            return [_to_result(chunk) for chunk in chunks]
        except (KeyError, TypeError) as exc:
            raise DocumentationQueryError(f"Unexpected RAGFLOW response shape: {exc}") from exc


def _to_result(chunk: dict) -> DocSearchResult:
    return DocSearchResult(
        source_path=chunk.get("document_keyword") or chunk.get("document_id", "unknown"),
        excerpt=(chunk.get("content") or "")[:400],
        score=float(chunk.get("similarity", 0.0)),
    )
