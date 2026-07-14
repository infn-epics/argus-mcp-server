"""Shared provider contract.

Every provider (EPICS, Archiver, ChannelFinder, Kubernetes, ArgoCD, Logbook,
Elasticsearch, Documentation) implements this in addition to its own
domain-specific interface. ``is_configured()`` must be cheap and side-effect
free (no network I/O) so ``AppContext.build()`` can construct every provider
unconditionally at startup, even when most of them have no config.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Protocol, runtime_checkable


class ProviderStatus(str, Enum):
    OK = "ok"
    UNCONFIGURED = "unconfigured"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    status: ProviderStatus
    detail: str | None = None


@runtime_checkable
class Provider(Protocol):
    name: ClassVar[str]

    def is_configured(self) -> bool: ...

    async def health(self) -> ProviderHealth: ...
