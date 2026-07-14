import asyncio

from argus.core.cache import AsyncTTLCache
from argus.providers.archiver.models import ArchiverSeries
from argus.providers.kubernetes.exceptions import KubernetesUnavailableError
from argus.services.device_service import DeviceService
from argus.services.diagnostics_service import DiagnosticsService


class _StubChannelFinder:
    """Configured, returns one channel with an ioc name so pod/pod_logs are
    actually attempted (not pre-skipped) in the tests below."""

    def is_configured(self) -> bool:
        return True

    async def find_channels(self, **kwargs):
        from argus.providers.channelfinder.models import CFChannel

        return [
            CFChannel(
                name="QF12:CURRENT",
                owner="ops",
                properties={"device": "QF12", "iocName": "ioc-qf12", "k8sNamespace": "accelerator"},
                tags=[],
            )
        ]


class _StubEpics:
    async def get_many(self, pv_names, timeout=5.0):
        from argus.providers.epics.models import PVValue

        return [PVValue(name=n, value=1.0) for n in pv_names]


class _StubArchiver:
    async def get_data(self, pv_name, start, end, timeout=5.0):
        return ArchiverSeries(pv_name=pv_name, samples=[])


class _StubKubernetesDown:
    async def get_pod_for_ioc(self, ioc_name, namespace):
        raise KubernetesUnavailableError("cluster unreachable")

    async def get_pod_logs(self, pod_name, namespace):
        raise KubernetesUnavailableError("cluster unreachable")


class _StubArgoCD:
    async def get_application(self, app_name):
        return None


class _StubLogbook:
    async def search_entries(self, text=None, tags=None, since=None, timeout=5.0):
        return []


class _StubDocumentation:
    async def search(self, query, top_k=3):
        return []


def _build_service(epics=None, archiver=None, kubernetes=None) -> DiagnosticsService:
    device_service = DeviceService(channelfinder=_StubChannelFinder(), cache=AsyncTTLCache(ttl=60))
    return DiagnosticsService(
        device_service=device_service,
        epics=epics or _StubEpics(),
        archiver=archiver or _StubArchiver(),
        kubernetes=kubernetes or _StubKubernetesDown(),
        argocd=_StubArgoCD(),
        logbook=_StubLogbook(),
        documentation=_StubDocumentation(),
    )


async def test_diagnose_device_degrades_when_kubernetes_down():
    service = _build_service()
    report = await service.diagnose_device("QF12", timeout=2)

    assert report.pod.status == "unavailable"
    assert report.pod_logs.status == "skipped"  # device has no known pod_name to begin with
    assert report.live_pvs.status == "ok"
    assert report.history.status == "ok"
    assert report.logbook.status == "ok"
    assert report.documentation.status == "ok"
    assert "pod" in report.degraded_providers
    assert "live_pvs" not in report.degraded_providers


async def test_diagnose_device_respects_per_provider_timeout():
    class _SlowArchiver:
        async def get_data(self, pv_name, start, end, timeout=5.0):
            await asyncio.sleep(10)
            return ArchiverSeries(pv_name=pv_name, samples=[])

    service = _build_service(archiver=_SlowArchiver())

    started = asyncio.get_event_loop().time()
    report = await service.diagnose_device("QF12", timeout=0.05)
    elapsed = asyncio.get_event_loop().time() - started

    assert report.history.status == "timeout"
    assert report.live_pvs.status == "ok"
    assert elapsed < 5  # never blocked on the slow provider past its own timeout


async def test_diagnose_device_never_raises_on_total_provider_failure():
    class _BrokenEpics:
        async def get_many(self, pv_names, timeout=5.0):
            raise RuntimeError("totally broken")

    service = _build_service(epics=_BrokenEpics())
    report = await service.diagnose_device("QF12", timeout=2)
    assert report.live_pvs.status == "error"
