"""Thin pass-through over SaveRestoreProvider -- kept as its own service
(rather than folded into e.g. HistoryService) since save-and-restore is its
own domain (configurations/snapshots), matching how knowledge_service and
beamline_inventory_service each own one domain.
"""

from __future__ import annotations

from argus.providers.saverestore.models import SnrConfiguration, SnrNode, SnrSnapshot
from argus.providers.saverestore.saverestore import SaveRestoreProvider


class SaveRestoreService:
    def __init__(self, saverestore: SaveRestoreProvider) -> None:
        self._saverestore = saverestore

    async def search(self, query: str) -> list[SnrNode]:
        return await self._saverestore.search(query)

    async def get_node(self, node_id: str) -> SnrNode:
        return await self._saverestore.get_node(node_id)

    async def get_children(self, node_id: str) -> list[SnrNode]:
        return await self._saverestore.get_children(node_id)

    async def get_configuration(self, config_id: str) -> SnrConfiguration:
        return await self._saverestore.get_configuration(config_id)

    async def get_snapshot(self, snapshot_id: str) -> SnrSnapshot:
        return await self._saverestore.get_snapshot(snapshot_id)
