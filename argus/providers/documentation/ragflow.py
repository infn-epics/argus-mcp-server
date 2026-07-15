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
"""

from __future__ import annotations

from typing import ClassVar

import httpx

from argus.config.settings import RagflowSettings
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

    async def search(self, query: str, top_k: int = 5, *, timeout: float | None = None) -> list[DocSearchResult]:
        self._require_configured()
        timeout = timeout if timeout is not None else self._settings.timeout_seconds
        body: dict = {"question": query, "page_size": top_k}
        if self._settings.dataset_ids:
            body["dataset_ids"] = [d.strip() for d in self._settings.dataset_ids.split(",") if d.strip()]

        url = f"{self._settings.base_url}/api/v1/retrieval"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.TimeoutException as exc:
            raise DocumentationTimeoutError(f"Timeout searching RAGFLOW for '{query}'") from exc
        except httpx.HTTPError as exc:
            raise DocumentationUnavailableError(f"RAGFLOW unreachable: {exc}") from exc

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
