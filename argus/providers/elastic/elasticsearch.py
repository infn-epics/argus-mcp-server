"""Elasticsearch provider for historical/aggregated application & IOC logs.

Distinct from the Kubernetes provider's live pod-log tail: this is for
searching across retained log history, using the official async client.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from argus.config.settings import ElasticSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.elastic.exceptions import (
    ElasticsearchQueryError,
    ElasticsearchTimeoutError,
    ElasticsearchUnavailableError,
    ElasticsearchUnconfiguredError,
)
from argus.providers.elastic.models import LogRecord


class ElasticsearchProvider:
    name: ClassVar[str] = "elasticsearch"

    def __init__(self, settings: ElasticSettings) -> None:
        self._settings = settings
        self._client: object | None = None

    def is_configured(self) -> bool:
        return bool(self._settings.url)

    def _get_client(self):
        if self._client is None:
            from elasticsearch import AsyncElasticsearch

            kwargs: dict = {"hosts": [self._settings.url]}
            if self._settings.api_key:
                kwargs["api_key"] = self._settings.api_key
            self._client = AsyncElasticsearch(**kwargs)
        return self._client

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            await self._get_client().ping()
            return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise ElasticsearchUnconfiguredError("Elasticsearch is not configured (set ELASTIC_URL).")

    async def search_logs(
        self,
        *,
        query: str,
        index: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        timeout: float = 8.0,
    ) -> list[LogRecord]:
        self._require_configured()
        index = index or self._settings.default_index

        must: list[dict] = [{"query_string": {"query": query}}]
        if since:
            must.append({"range": {"@timestamp": {"gte": since.isoformat()}}})

        body = {"query": {"bool": {"must": must}}, "size": limit, "sort": [{"@timestamp": "desc"}]}

        try:
            response = await self._get_client().search(index=index, body=body, request_timeout=timeout)
        except TimeoutError as exc:
            raise ElasticsearchTimeoutError(f"Timeout searching Elasticsearch index '{index}'") from exc
        except Exception as exc:  # noqa: BLE001
            raise ElasticsearchUnavailableError(f"Elasticsearch unreachable: {exc}") from exc

        try:
            hits = response["hits"]["hits"]
            return [_to_log_record(hit) for hit in hits]
        except (KeyError, TypeError) as exc:
            raise ElasticsearchQueryError(f"Unexpected Elasticsearch response shape: {exc}") from exc


def _to_log_record(hit: dict) -> LogRecord:
    source = hit.get("_source", {})
    timestamp = source.get("@timestamp")
    return LogRecord(
        timestamp=datetime.fromisoformat(timestamp) if timestamp else None,
        source=source.get("kubernetes", {}).get("pod_name") if isinstance(source.get("kubernetes"), dict) else None,
        message=source.get("message", ""),
        level=source.get("level"),
        raw=source,
    )
