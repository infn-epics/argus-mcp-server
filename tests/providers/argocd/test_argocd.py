import httpx
import pytest
import respx

from argus.config.settings import ArgoCDSettings
from argus.providers.argocd.argocd import ArgoCDProvider
from argus.providers.argocd.exceptions import ArgoCDAuthError, ArgoCDUnconfiguredError


def _configured() -> ArgoCDProvider:
    return ArgoCDProvider(ArgoCDSettings(_env_file=None, ARGOCD_SERVER_URL="http://argocd.test"))


async def test_unconfigured_raises_clean_error():
    provider = ArgoCDProvider(ArgoCDSettings(_env_file=None))
    with pytest.raises(ArgoCDUnconfiguredError):
        await provider.get_application("ioc-qf12")


@respx.mock
async def test_get_application_parses_status():
    provider = _configured()
    respx.get("http://argocd.test/api/v1/applications/ioc-qf12").mock(
        return_value=httpx.Response(
            200,
            json={
                "metadata": {"name": "ioc-qf12"},
                "status": {"sync": {"status": "Synced", "revision": "abc123"}, "health": {"status": "Healthy"}},
                "spec": {"source": {"repoURL": "https://git.example.org/iocs/qf12"}},
            },
        )
    )
    status = await provider.get_application("ioc-qf12")
    assert status.sync_status == "Synced"
    assert status.health_status == "Healthy"
    assert status.repo_url == "https://git.example.org/iocs/qf12"


@respx.mock
async def test_get_application_returns_none_on_404():
    provider = _configured()
    respx.get("http://argocd.test/api/v1/applications/missing").mock(return_value=httpx.Response(404))
    assert await provider.get_application("missing") is None


@respx.mock
async def test_get_application_auth_error_on_401():
    provider = _configured()
    respx.get("http://argocd.test/api/v1/applications/ioc-qf12").mock(return_value=httpx.Response(401))
    with pytest.raises(ArgoCDAuthError):
        await provider.get_application("ioc-qf12")
