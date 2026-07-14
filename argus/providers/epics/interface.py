"""Common protocol implemented by both the Channel Access and pvAccess adapters.

operations_service depends on this Protocol, not on either concrete adapter,
so it can try Channel Access first and fall back to pvAccess (or vice versa
per EPICS_PROTOCOL_OVERRIDES) without knowing which one it's talking to.
"""

from __future__ import annotations

from typing import Any, Protocol

from argus.providers.base import Provider
from argus.providers.epics.models import PVInfo, PVValue, PVWriteResult


class EpicsProvider(Provider, Protocol):
    async def get(self, pv_name: str, timeout: float = 5.0) -> PVValue: ...

    async def put(self, pv_name: str, value: Any, timeout: float = 5.0) -> PVWriteResult: ...

    async def info(self, pv_name: str, timeout: float = 5.0) -> PVInfo: ...

    async def get_many(self, pv_names: list[str], timeout: float = 5.0) -> list[PVValue]: ...
