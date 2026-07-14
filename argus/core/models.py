"""Cross-cutting result types used by every service that fans out across providers."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

import structlog

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError

logger = structlog.get_logger(__name__)

T = TypeVar("T")

ProviderStatusLiteral = Literal["ok", "unconfigured", "unavailable", "timeout", "error", "skipped"]


@dataclass
class ProviderResult(Generic[T]):
    """The outcome of one provider call, never an exception.

    Every fan-out in the service layer produces a mapping of these instead of
    letting a single failing backend take down the whole response — this is the
    concrete mechanism behind "gracefully degrade if one backend is unavailable".
    """

    provider: str
    status: ProviderStatusLiteral
    data: T | None = None
    error: str | None = None
    latency_ms: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def skipped(provider: str, reason: str = "not applicable for this device") -> ProviderResult:
    """A ProviderResult for a call that was never attempted (e.g. no pod_name known)."""
    return ProviderResult(provider=provider, status="skipped", error=reason)


async def _run_one(provider: str, backend: str, awaitable: Awaitable[T], timeout: float) -> ProviderResult[T]:
    start = time.perf_counter()
    try:
        data = await asyncio.wait_for(awaitable, timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000
        logger.info("provider_call", provider=provider, backend=backend, latency_ms=round(latency_ms, 2), status="ok")
        return ProviderResult(provider=provider, status="ok", data=data, latency_ms=latency_ms)
    except TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning("provider_call", provider=provider, backend=backend, latency_ms=round(latency_ms, 2), status="timeout")
        return ProviderResult(provider=provider, status="timeout", error=f"timed out after {timeout}s", latency_ms=latency_ms)
    except ProviderUnconfiguredError as exc:
        logger.info("provider_call", provider=provider, backend=backend, status="unconfigured")
        return ProviderResult(provider=provider, status="unconfigured", error=str(exc))
    except (ProviderUnavailableError, ProviderTimeoutError) as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning("provider_call", provider=provider, backend=backend, latency_ms=round(latency_ms, 2), status="unavailable")
        return ProviderResult(provider=provider, status="unavailable", error=str(exc), latency_ms=latency_ms)
    except ArgusError as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning("provider_call", provider=provider, backend=backend, latency_ms=round(latency_ms, 2), status="error", error=str(exc))
        return ProviderResult(provider=provider, status="error", error=str(exc), latency_ms=latency_ms)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is the degradation boundary
        latency_ms = (time.perf_counter() - start) * 1000
        logger.exception("provider_call_unexpected", provider=provider, backend=backend, latency_ms=round(latency_ms, 2))
        return ProviderResult(provider=provider, status="error", error=str(exc), latency_ms=latency_ms)


async def gather_with_timeout(
    coro_map: Mapping[str, Awaitable[T]],
    timeout: float,
    *,
    backend_map: Mapping[str, str] | None = None,
) -> dict[str, ProviderResult[T]]:
    """Run every coroutine in ``coro_map`` concurrently, each under its own timeout.

    A failing or slow provider never cancels the others and never raises out of this
    function — every entry always yields a ``ProviderResult``. ``backend_map`` lets
    callers attach a human-readable backend name (e.g. "kubernetes api") for logging.
    """
    backend_map = backend_map or {}
    keys = list(coro_map.keys())
    results = await asyncio.gather(
        *(
            _run_one(key, backend_map.get(key, key), coro_map[key], timeout)
            for key in keys
        )
    )
    return dict(zip(keys, results, strict=True))
