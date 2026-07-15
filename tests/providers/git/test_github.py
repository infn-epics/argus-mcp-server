import base64

import httpx
import pytest
import respx

from argus.config.settings import GitHubSettings
from argus.providers.git.exceptions import GitHubNotFoundError, GitHubUnavailableError, GitHubUnconfiguredError
from argus.providers.git.github import GitHubProvider


def _configured() -> GitHubProvider:
    return GitHubProvider(GitHubSettings(_env_file=None, GITHUB_TOKEN="ghp_test"))


async def test_unconfigured_raises_clean_error():
    provider = GitHubProvider(GitHubSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(GitHubUnconfiguredError):
        await provider.get_file("https://github.com/infn-epics/ioc-chart.git", "README.md")


@respx.mock
async def test_get_file_decodes_base64_content():
    provider = _configured()
    encoded = base64.b64encode(b"hello world").decode()
    respx.get("https://api.github.com/repos/infn-epics/ioc-chart/contents/README.md").mock(
        return_value=httpx.Response(200, json={"content": encoded, "sha": "abc123"})
    )
    result = await provider.get_file("https://github.com/infn-epics/ioc-chart.git", "README.md")
    assert result.content == "hello world"
    assert result.sha == "abc123"


@respx.mock
async def test_get_file_404_raises_not_found():
    provider = _configured()
    respx.get("https://api.github.com/repos/infn-epics/ioc-chart/contents/missing.txt").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(GitHubNotFoundError):
        await provider.get_file("https://github.com/infn-epics/ioc-chart.git", "missing.txt")


@respx.mock
async def test_get_history_parses_commits():
    provider = _configured()
    respx.get("https://api.github.com/repos/infn-epics/ioc-chart/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "sha": "deadbeef",
                    "commit": {"author": {"name": "A. Michelotti", "date": "2026-06-01T10:00:00Z"}, "message": "fix motor template"},
                    "html_url": "https://github.com/infn-epics/ioc-chart/commit/deadbeef",
                }
            ],
        )
    )
    history = await provider.get_history("https://github.com/infn-epics/ioc-chart.git", "values.yaml")
    assert history[0].sha == "deadbeef"
    assert history[0].message == "fix motor template"


@respx.mock
async def test_search_issues_scopes_query_to_repo():
    provider = _configured()
    route = respx.get("https://api.github.com/search/issues").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"number": 42, "title": "motor stuck", "state": "closed", "html_url": "https://x", "labels": [{"name": "bug"}]}]},
        )
    )
    results = await provider.search_issues("https://github.com/infn-epics/ioc-chart.git", "motor stuck")
    assert results[0].id == "42"
    assert results[0].labels == ["bug"]
    assert "repo:infn-epics/ioc-chart" in route.calls[0].request.url.params["q"]


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.get("https://api.github.com/repos/infn-epics/ioc-chart/contents/README.md").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with pytest.raises(GitHubUnavailableError):
        await provider.get_file("https://github.com/infn-epics/ioc-chart.git", "README.md")
