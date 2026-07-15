import pytest

from argus.config.settings import GitHubSettings, GitLabSettings
from argus.providers.git.exceptions import UnsupportedGitHostError
from argus.providers.git.github import GitHubProvider
from argus.providers.git.gitlab import GitLabProvider
from argus.providers.git.models import CommitInfo, Issue
from argus.services.knowledge_service import KnowledgeService


class _FakeGitHub(GitHubProvider):
    def __init__(self):
        super().__init__(GitHubSettings(_env_file=None, GITHUB_TOKEN="tok"))
        self.calls = []

    async def get_history(self, repo, path, limit=20):
        self.calls.append(("history", repo, path))
        return [CommitInfo(sha="gh1", author="a", date=None, message="from github")]

    async def search_issues(self, repo, query, state="all", limit=20):
        self.calls.append(("search", repo, query))
        return [Issue(id="1", repo=repo, title="gh issue", state="open", url="https://x")]


class _FakeGitLab(GitLabProvider):
    def __init__(self):
        super().__init__(GitLabSettings(_env_file=None, GITLAB_BASE_URL="https://baltig.infn.it", GITLAB_TOKEN="tok"))
        self.calls = []

    async def get_history(self, repo, path, limit=20):
        self.calls.append(("history", repo, path))
        return [CommitInfo(sha="gl1", author="a", date=None, message="from gitlab")]

    async def search_issues(self, repo, query, state="all", limit=20):
        self.calls.append(("search", repo, query))
        return [Issue(id="7", repo=repo, title="gl issue", state="open", url="https://y")]


@pytest.fixture
def github():
    return _FakeGitHub()


@pytest.fixture
def gitlab():
    return _FakeGitLab()


async def test_routes_github_urls_to_github_provider(github, gitlab):
    service = KnowledgeService(github=github, gitlab=gitlab)
    history = await service.get_config_history("https://github.com/infn-epics/ioc-chart.git", "values.yaml")
    assert history[0].sha == "gh1"
    assert github.calls[0][0] == "history"
    assert not gitlab.calls


async def test_routes_gitlab_urls_to_gitlab_provider(github, gitlab):
    service = KnowledgeService(github=github, gitlab=gitlab)
    history = await service.get_config_history("https://baltig.infn.it/lnf-da-control/epik8s-btf.git", "deploy/values.yaml")
    assert history[0].sha == "gl1"
    assert gitlab.calls[0][0] == "history"
    assert not github.calls


async def test_unknown_host_raises_unsupported_error(github, gitlab):
    service = KnowledgeService(github=github, gitlab=gitlab)
    with pytest.raises(UnsupportedGitHostError):
        await service.get_config_history("https://gitea.example.org/x/y.git", "values.yaml")


async def test_search_knowledge_base_fans_out_across_both_platforms(github, gitlab):
    service = KnowledgeService(github=github, gitlab=gitlab)
    issues = await service.search_knowledge_base(
        "magnet interlock",
        repos=[
            "https://github.com/infn-epics/ioc-chart.git",
            "https://baltig.infn.it/lnf-da-control/epik8s-btf.git",
        ],
    )
    ids = {i.id for i in issues}
    assert ids == {"1", "7"}


async def test_search_knowledge_base_uses_default_repos_when_none_given(github, gitlab):
    service = KnowledgeService(
        github=github, gitlab=gitlab, default_repos=["https://github.com/infn-epics/ioc-chart.git"]
    )
    issues = await service.search_knowledge_base("magnet interlock")
    assert len(issues) == 1
    assert issues[0].repo == "https://github.com/infn-epics/ioc-chart.git"


async def test_search_knowledge_base_returns_empty_without_repos(github, gitlab):
    service = KnowledgeService(github=github, gitlab=gitlab)
    assert await service.search_knowledge_base("anything") == []
