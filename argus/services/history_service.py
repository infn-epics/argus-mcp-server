"""Historical data: archiver trends, alarm/maintenance history, log search.

Alarm and maintenance history are modeled as Logbook entries filtered by tag
convention (tag=alarm, tag=maintenance) rather than inventing a dedicated
provider — the spec's provider list has none, and Logbook already fits.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argus.providers.archiver.archiver_appliance import ArchiverApplianceProvider
from argus.providers.archiver.models import ArchiverSeries
from argus.providers.elastic.elasticsearch import ElasticsearchProvider
from argus.providers.elastic.models import LogRecord
from argus.providers.logbook.logbook import LogbookProvider
from argus.providers.logbook.models import LogbookEntry


class HistoryService:
    def __init__(
        self,
        archiver: ArchiverApplianceProvider,
        logbook: LogbookProvider,
        elastic: ElasticsearchProvider,
    ) -> None:
        self._archiver = archiver
        self._logbook = logbook
        self._elastic = elastic

    async def get_history(self, pv_name: str, start: datetime, end: datetime) -> ArchiverSeries:
        return await self._archiver.get_data(pv_name, start, end)

    async def get_alarm_history(self, device_name: str, since: datetime | None = None) -> list[LogbookEntry]:
        since = since or datetime.now(timezone.utc) - timedelta(days=7)
        return await self._logbook.search_entries(text=device_name, tags=["alarm"], since=since)

    async def get_maintenance_history(self, device_name: str, since: datetime | None = None) -> list[LogbookEntry]:
        since = since or datetime.now(timezone.utc) - timedelta(days=30)
        return await self._logbook.search_entries(text=device_name, tags=["maintenance"], since=since)

    async def get_logs(
        self, query: str, *, index: str | None = None, since: datetime | None = None, limit: int = 100
    ) -> list[LogRecord]:
        return await self._elastic.search_logs(query=query, index=index, since=since, limit=limit)
