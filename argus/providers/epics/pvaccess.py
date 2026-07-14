"""pvAccess provider, built on p4p's native asyncio client.

Used for PVs only reachable over pvAccess (e.g. structured/NTTable data from
newer IOCs). Implements the same EpicsProvider protocol as the Channel Access
adapter so operations_service can fall back to this transparently.
"""

from __future__ import annotations

from typing import Any, ClassVar

from argus.config.settings import EpicsSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.epics.exceptions import (
    EpicsConnectionError,
    EpicsTimeoutError,
    EpicsUnconfiguredError,
    PVWriteRejectedError,
)
from argus.providers.epics.models import PVInfo, PVValue, PVWriteResult


class PvAccessProvider:
    """EpicsProvider implementation backed by p4p (pvAccess protocol)."""

    name: ClassVar[str] = "epics_pva"

    def __init__(self, settings: EpicsSettings) -> None:
        self._settings = settings
        self._context: Any | None = None

    def is_configured(self) -> bool:
        return bool(self._settings.pva_addr_list)

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            import p4p  # noqa: F401
        except ImportError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.OK)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise EpicsUnconfiguredError(
                "EPICS pvAccess is not configured (set EPICS_PVA_ADDR_LIST)."
            )

    def _get_context(self) -> Any:
        if self._context is None:
            import os

            from p4p.client.asyncio import Context

            if self._settings.pva_addr_list:
                os.environ.setdefault("EPICS_PVA_ADDR_LIST", self._settings.pva_addr_list)
            self._context = Context("pva")
        return self._context

    async def get(self, pv_name: str, timeout: float = 5.0) -> PVValue:
        self._require_configured()
        ctx = self._get_context()
        try:
            result = await ctx.get(pv_name, timeout=timeout)
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while getting PV '{pv_name}' over pvAccess") from exc
        except Exception as exc:  # noqa: BLE001 - p4p raises various RemoteError subtypes
            raise EpicsConnectionError(f"Failed to get PV '{pv_name}' over pvAccess: {exc}") from exc

        return PVValue(
            name=pv_name,
            value=_unwrap_value(result),
            timestamp=_extract_timestamp(result),
            severity=_extract_alarm_field(result, "severity"),
            status=_extract_alarm_field(result, "status"),
        )

    async def put(self, pv_name: str, value: Any, timeout: float = 5.0) -> PVWriteResult:
        self._require_configured()
        ctx = self._get_context()
        try:
            await ctx.put(pv_name, value, timeout=timeout)
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while setting PV '{pv_name}' over pvAccess") from exc
        except Exception as exc:  # noqa: BLE001
            raise PVWriteRejectedError(f"Failed to set PV '{pv_name}' to {value!r} over pvAccess: {exc}") from exc

        return PVWriteResult(name=pv_name, accepted=True, new_value=value)

    async def info(self, pv_name: str, timeout: float = 5.0) -> PVInfo:
        self._require_configured()
        ctx = self._get_context()
        try:
            result = await ctx.get(pv_name, timeout=timeout)
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while getting info for PV '{pv_name}' over pvAccess") from exc
        except Exception as exc:  # noqa: BLE001
            raise EpicsConnectionError(f"Failed to get info for PV '{pv_name}' over pvAccess: {exc}") from exc

        return PVInfo(
            name=pv_name,
            native_type=type(_unwrap_value(result)).__name__,
            units=_get_field(result, "display.units"),
            precision=_get_field(result, "display.precision"),
        )

    async def get_many(self, pv_names: list[str], timeout: float = 5.0) -> list[PVValue]:
        self._require_configured()
        ctx = self._get_context()
        try:
            results = await ctx.get(pv_names, timeout=timeout, throw=False)
        except TimeoutError as exc:
            raise EpicsTimeoutError("Timeout while getting multiple PVs over pvAccess") from exc

        values: list[PVValue] = []
        for name, result in zip(pv_names, results, strict=True):
            if isinstance(result, Exception):
                values.append(PVValue(name=name, value=None, status="disconnected"))
            else:
                values.append(
                    PVValue(
                        name=name,
                        value=_unwrap_value(result),
                        timestamp=_extract_timestamp(result),
                        severity=_extract_alarm_field(result, "severity"),
                    )
                )
        return values


def _unwrap_value(result: Any) -> Any:
    try:
        return result.value if hasattr(result, "value") else result
    except Exception:  # noqa: BLE001
        return result


def _extract_timestamp(result: Any) -> Any:
    return _get_field(result, "timeStamp")


def _extract_alarm_field(result: Any, field: str) -> str | None:
    value = _get_field(result, f"alarm.{field}")
    return str(value) if value is not None else None


def _get_field(result: Any, path: str) -> Any:
    try:
        return result[path]
    except Exception:  # noqa: BLE001
        return None
