"""Channel Access provider, built on aioca (asyncio-native CA client).

The original PoC called pyepics's blocking ``caget``/``caput``/``cainfo``
directly on the event loop. aioca gives real async CA I/O (same underlying
libca), so ``get_many`` genuinely fans out concurrently instead of running
N sequential blocking calls.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar

from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.epics.exceptions import (
    EpicsConnectionError,
    EpicsTimeoutError,
    EpicsUnconfiguredError,
    PVWriteRejectedError,
)
from argus.providers.epics.models import PVInfo, PVValue, PVWriteResult
from argus.config.settings import EpicsSettings


class ChannelAccessProvider:
    """EpicsProvider implementation backed by aioca."""

    name: ClassVar[str] = "epics_ca"

    def __init__(self, settings: EpicsSettings) -> None:
        self._settings = settings
        if settings.ca_addr_list:
            os.environ.setdefault("EPICS_CA_ADDR_LIST", settings.ca_addr_list)
            os.environ.setdefault("EPICS_CA_AUTO_ADDR_LIST", "YES" if settings.ca_auto_addr_list else "NO")

    def is_configured(self) -> bool:
        return bool(self._settings.ca_addr_list)

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            import aioca  # noqa: F401
        except ImportError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.OK)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise EpicsUnconfiguredError(
                "EPICS Channel Access is not configured (set EPICS_CA_ADDR_LIST)."
            )

    async def get(self, pv_name: str, timeout: float = 5.0) -> PVValue:
        self._require_configured()
        from aioca import FORMAT_TIME, CANothing, caget

        try:
            result = await caget(pv_name, format=FORMAT_TIME, timeout=timeout)
        except CANothing as exc:
            raise EpicsConnectionError(f"Failed to get PV '{pv_name}': {exc}") from exc
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while getting PV '{pv_name}'") from exc

        return PVValue(
            name=pv_name,
            value=result,
            timestamp=getattr(result, "timestamp", None),
            severity=str(getattr(result, "severity", None)) if getattr(result, "severity", None) is not None else None,
            status=str(getattr(result, "status", None)) if getattr(result, "status", None) is not None else None,
        )

    async def put(self, pv_name: str, value: Any, timeout: float = 5.0) -> PVWriteResult:
        self._require_configured()
        from aioca import CANothing, caput

        try:
            await caput(pv_name, value, timeout=timeout)
        except CANothing as exc:
            raise PVWriteRejectedError(f"Failed to set PV '{pv_name}' to {value!r}: {exc}") from exc
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while setting PV '{pv_name}'") from exc

        return PVWriteResult(name=pv_name, accepted=True, new_value=value)

    async def info(self, pv_name: str, timeout: float = 5.0) -> PVInfo:
        self._require_configured()
        from aioca import FORMAT_CTRL, CANothing, cainfo, caget

        try:
            info = await cainfo(pv_name, timeout=timeout)
        except CANothing as exc:
            raise EpicsConnectionError(f"Failed to get info for PV '{pv_name}': {exc}") from exc
        except TimeoutError as exc:
            raise EpicsTimeoutError(f"Timeout while getting info for PV '{pv_name}'") from exc

        native_type = info.datatype_strings[info.datatype] if 0 <= info.datatype < len(info.datatype_strings) else None
        access = f"read={info.read}, write={info.write}"

        units = precision = None
        display_limits = alarm_limits = None
        try:
            ctrl = await caget(pv_name, format=FORMAT_CTRL, timeout=timeout, throw=False)
            if getattr(ctrl, "ok", False):
                units = getattr(ctrl, "units", None)
                precision = getattr(ctrl, "precision", None)
                display_limits = _limits(ctrl, "lower_disp_limit", "upper_disp_limit")
                alarm_limits = _limits(ctrl, "lower_alarm_limit", "upper_alarm_limit")
        except (CANothing, TimeoutError):
            pass  # host/access info is still useful even if CTRL fields aren't available

        return PVInfo(
            name=pv_name,
            native_type=native_type,
            element_count=info.count,
            host=info.host,
            access=access,
            units=units,
            precision=precision,
            display_limits=display_limits,
            alarm_limits=alarm_limits,
        )

    async def get_many(self, pv_names: list[str], timeout: float = 5.0) -> list[PVValue]:
        self._require_configured()
        from aioca import FORMAT_TIME, caget

        results = await caget(pv_names, format=FORMAT_TIME, timeout=timeout, throw=False)
        values: list[PVValue] = []
        for name, result in zip(pv_names, results, strict=True):
            ok = getattr(result, "ok", True)
            values.append(
                PVValue(
                    name=name,
                    value=result if ok else None,
                    timestamp=getattr(result, "timestamp", None) if ok else None,
                    severity=str(getattr(result, "severity", None)) if ok and getattr(result, "severity", None) is not None else None,
                    status="disconnected" if not ok else None,
                )
            )
        return values


def _limits(result: Any, lower_attr: str, upper_attr: str) -> tuple[float, float] | None:
    import math

    lower = getattr(result, lower_attr, None)
    upper = getattr(result, upper_attr, None)
    if lower is None or upper is None:
        return None
    # EPICS reports unset CTRL limits as NaN, not absence — NaN isn't valid JSON.
    if isinstance(lower, float) and math.isnan(lower):
        return None
    if isinstance(upper, float) and math.isnan(upper):
        return None
    return (lower, upper)
