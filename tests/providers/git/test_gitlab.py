import base64

import httpx
import pytest
import respx

from argus.config.settings import GitLabSettings
from argus.providers.git.exceptions import GitLabNotFoundError, GitLabUnavailableError, GitLabUnconfiguredError
from argus.providers.git.gitlab import GitLabProvider


def _configured() -> GitLabProvider:
    return GitLabProvider(GitLabSettings(_env_file=None, GITLAB_BASE_URL="https://baltig.infn.it", GITLAB_TOKEN="glpat-test"))


async def test_unconfigured_raises_clean_error():
    provider = GitLabProvider(GitLabSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(GitLabUnconfiguredError):
        await provider.get_file("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "deploy/values.yaml")


@respx.mock
async def test_get_file_decodes_base64_content():
    provider = _configured()
    encoded = base64.b64encode(b"beamline: BTF").decode()
    respx.get(
        "https://baltig.infn.it/api/v4/projects/lnf-da-control%2Fepik8s-btf/repository/files/deploy%2Fvalues.yaml"
    ).mock(return_value=httpx.Response(200, json={"content": encoded, "blob_id": "xyz"}))
    result = await provider.get_file("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "deploy/values.yaml")
    assert result.content == "beamline: BTF"
    assert result.sha == "xyz"


@respx.mock
async def test_get_file_404_raises_not_found():
    provider = _configured()
    respx.get(
        "https://baltig.infn.it/api/v4/projects/lnf-da-control%2Fepik8s-btf/repository/files/missing.yaml"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(GitLabNotFoundError):
        await provider.get_file("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "missing.yaml")


@respx.mock
async def test_get_history_parses_commits():
    provider = _configured()
    respx.get("https://baltig.infn.it/api/v4/projects/lnf-da-control%2Fepik8s-btf/repository/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "cafef00d",
                    "author_name": "A. Michelotti",
                    "authored_date": "2026-06-01T10:00:00.000+00:00",
                    "message": "add argus service",
                    "web_url": "https://baltig.infn.it/lnf-da-control/epik8s-btf/-/commit/cafef00d",
                }
            ],
        )
    )
    history = await provider.get_history("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "deploy/values.yaml")
    assert history[0].sha == "cafef00d"
    assert history[0].message == "add argus service"


@respx.mock
async def test_search_issues_parses_state_and_labels():
    provider = _configured()
    respx.get("https://baltig.infn.it/api/v4/projects/lnf-da-control%2Fepik8s-btf/issues").mock(
        return_value=httpx.Response(
            200,
            json=[{"iid": 7, "title": "gateway down", "state": "closed", "web_url": "https://x", "labels": ["incident"]}],
        )
    )
    results = await provider.search_issues("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "gateway down")
    assert results[0].id == "7"
    assert results[0].labels == ["incident"]


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.get(
        "https://baltig.infn.it/api/v4/projects/lnf-da-control%2Fepik8s-btf/repository/files/deploy%2Fvalues.yaml"
    ).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(GitLabUnavailableError):
        await provider.get_file("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "deploy/values.yaml")
