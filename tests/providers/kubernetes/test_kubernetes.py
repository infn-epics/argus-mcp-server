from types import SimpleNamespace

import pytest

from argus.config.settings import KubernetesSettings
from argus.providers.kubernetes.exceptions import KubernetesUnconfiguredError
from argus.providers.kubernetes.kubernetes import KubernetesProvider


def _fake_pod(name="ioc-qf12-abcde", namespace="accelerator", phase="Running", ready="True", restarts=0):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, namespace=namespace),
        status=SimpleNamespace(
            phase=phase,
            conditions=[SimpleNamespace(type="Ready", status=ready)],
            container_statuses=[SimpleNamespace(restart_count=restarts)],
            start_time=None,
        ),
        spec=SimpleNamespace(node_name="node-1"),
    )


def test_unconfigured_when_no_kubeconfig_and_not_in_cluster(monkeypatch):
    import kubernetes.config

    def _raise(*a, **k):
        raise kubernetes.config.ConfigException("no config found")

    monkeypatch.setattr(kubernetes.config, "load_incluster_config", _raise)
    monkeypatch.setattr(kubernetes.config, "load_kube_config", _raise)

    provider = KubernetesProvider(KubernetesSettings(_env_file=None))
    assert provider.is_configured() is False


async def test_require_configured_raises_clean_error(monkeypatch):
    import kubernetes.config

    def _raise(*a, **k):
        raise kubernetes.config.ConfigException("no config found")

    monkeypatch.setattr(kubernetes.config, "load_incluster_config", _raise)
    monkeypatch.setattr(kubernetes.config, "load_kube_config", _raise)

    provider = KubernetesProvider(KubernetesSettings(_env_file=None))
    with pytest.raises(KubernetesUnconfiguredError):
        await provider.list_iocs()


async def test_list_iocs_converts_pods(monkeypatch):
    monkeypatch.setattr("kubernetes.config.load_incluster_config", lambda: None)

    provider = KubernetesProvider(KubernetesSettings(_env_file=None))
    assert provider.is_configured() is True

    fake_api = SimpleNamespace(
        list_namespaced_pod=lambda ns, label_selector=None: SimpleNamespace(items=[_fake_pod()])
    )
    provider._api = fake_api

    pods = await provider.list_iocs(namespace="accelerator")
    assert pods[0].name == "ioc-qf12-abcde"
    assert pods[0].ready is True
    assert pods[0].phase == "Running"
