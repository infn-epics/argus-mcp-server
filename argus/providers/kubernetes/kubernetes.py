"""Kubernetes provider, built on the official ``kubernetes`` client.

The official client is synchronous, so every call is offloaded to a thread via
``asyncio.to_thread`` rather than pulling in a separate async k8s library —
simplest option that still satisfies the async requirement.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from argus.config.settings import KubernetesSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.kubernetes.exceptions import (
    KubernetesResourceNotFoundError,
    KubernetesUnavailableError,
    KubernetesUnconfiguredError,
)
from argus.providers.kubernetes.models import PodStatus


class KubernetesProvider:
    name: ClassVar[str] = "kubernetes"

    def __init__(self, settings: KubernetesSettings) -> None:
        self._settings = settings
        self._configured = self._try_load_config()
        self._api: Any | None = None

    def _try_load_config(self) -> bool:
        try:
            from kubernetes import config

            if self._settings.kubeconfig_path:
                config.load_kube_config(config_file=self._settings.kubeconfig_path)
            else:
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()
            return True
        except Exception:  # noqa: BLE001 - any failure here just means "unconfigured"
            return False

    def is_configured(self) -> bool:
        return self._configured

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            await asyncio.to_thread(self._core_v1().get_api_resources)
            return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise KubernetesUnconfiguredError(
                "Kubernetes is not configured (no KUBECONFIG and not running in-cluster)."
            )

    def _core_v1(self) -> Any:
        if self._api is None:
            from kubernetes.client import CoreV1Api

            self._api = CoreV1Api()
        return self._api

    def _namespace_or_default(self, namespace: str | None) -> str:
        return namespace or self._settings.default_namespace

    async def get_pod_for_ioc(self, ioc_name: str, namespace: str | None = None) -> PodStatus | None:
        self._require_configured()
        ns = self._namespace_or_default(namespace)
        selector = self._settings.ioc_label_selector_template.format(ioc_name=ioc_name)
        pods = await self.list_iocs(namespace=ns, label_selector=selector)
        return pods[0] if pods else None

    async def list_iocs(self, namespace: str | None = None, *, label_selector: str | None = None) -> list[PodStatus]:
        self._require_configured()
        ns = self._namespace_or_default(namespace)
        try:
            result = await asyncio.to_thread(
                self._core_v1().list_namespaced_pod, ns, label_selector=label_selector
            )
        except Exception as exc:  # noqa: BLE001
            raise KubernetesUnavailableError(f"Kubernetes API unreachable: {exc}") from exc

        return [_to_pod_status(item) for item in result.items]

    async def get_pod_logs(self, pod_name: str, namespace: str, tail_lines: int = 200) -> str:
        self._require_configured()
        try:
            return await asyncio.to_thread(
                self._core_v1().read_namespaced_pod_log, pod_name, namespace, tail_lines=tail_lines
            )
        except Exception as exc:  # noqa: BLE001
            raise KubernetesResourceNotFoundError(f"Could not read logs for pod '{pod_name}': {exc}") from exc

    async def restart_pod(self, pod_name: str, namespace: str) -> bool:
        self._require_configured()
        try:
            await asyncio.to_thread(self._core_v1().delete_namespaced_pod, pod_name, namespace)
        except Exception as exc:  # noqa: BLE001
            raise KubernetesResourceNotFoundError(f"Could not restart pod '{pod_name}': {exc}") from exc
        return True


def _to_pod_status(pod: Any) -> PodStatus:
    status = pod.status
    conditions = {c.type: c.status for c in (status.conditions or [])}
    restart_count = sum(cs.restart_count for cs in (status.container_statuses or []))
    return PodStatus(
        name=pod.metadata.name,
        namespace=pod.metadata.namespace,
        phase=status.phase,
        ready=conditions.get("Ready") == "True",
        restart_count=restart_count,
        node=pod.spec.node_name if pod.spec else None,
        started_at=status.start_time,
    )
