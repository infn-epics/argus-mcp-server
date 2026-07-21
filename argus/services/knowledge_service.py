"""Config history and issue/ticket knowledge base, spanning GitHub and GitLab.

Every method accepts a plain git URL (the same charturl/giturl values already
used throughout epik8s deployment configs) as its `repo` argument — routing
to the right provider is based on the URL's host, mirroring how
OperationsService picks Channel Access vs pvAccess per PV.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from argus.core.cache import AsyncTTLCache
from argus.core.errors import ValidationError
from argus.core.models import gather_with_timeout
from argus.providers.git.exceptions import UnsupportedGitHostError
from argus.providers.git.github import GitHubProvider
from argus.providers.git.gitlab import GitLabProvider
from argus.providers.git.interface import GitProvider
from argus.providers.git.models import CommitInfo, FileContent, FileDiff, Issue


class KnowledgeService:
    def __init__(
        self,
        github: GitHubProvider,
        gitlab: GitLabProvider,
        default_repos: list[str] | None = None,
        default_ref: str = "HEAD",
        cache: AsyncTTLCache | None = None,
    ) -> None:
        self._github = github
        self._gitlab = gitlab
        self._default_repos = default_repos or []
        self._default_ref = default_ref
        self._cache = cache or AsyncTTLCache(ttl=600.0)

    def _provider_for(self, repo: str) -> GitProvider:
        host = urlparse(repo).netloc if "://" in repo else repo.split("/")[0]
        if host == "github.com":
            return self._github
        gitlab_host = urlparse(self._gitlab.base_url).netloc if self._gitlab.base_url else None
        if gitlab_host and host == gitlab_host:
            return self._gitlab
        raise UnsupportedGitHostError(
            f"'{host}' is not github.com and doesn't match the configured GitLab host — "
            "add a GitLab base URL for this host, or this repo can't be reached."
        )

    def _resolve_repo(self, repo: str | None) -> str:
        """Same "fall back to the configured default" behavior search_knowledge_base
        already had — a single-repo caller (get_file/get_config_history/get_commit_diff)
        almost always means "this beamline's own repo" (GIT_DEFAULT_REPOS), not a repo
        the caller has to already know the URL of."""
        if repo:
            return repo
        if self._default_repos:
            return self._default_repos[0]
        raise ValidationError(
            "repo was not given and no default repo is configured (GIT_DEFAULT_REPOS) - pass repo explicitly."
        )

    def _resolve_ref(self, ref: str | None) -> str:
        """A caller-passed "HEAD" (the documented convention for "current version",
        see knowledge_tools.py) or an omitted ref both mean the same thing: read
        whatever this beamline is actually deployed from (GIT_DEFAULT_REF), not
        git's own literal HEAD (the repo's default branch) -- those differ for any
        beamline pinned to a non-default branch."""
        if ref and ref != "HEAD":
            return ref
        return self._default_ref

    async def get_file(self, repo: str | None, path: str, ref: str | None = "HEAD") -> FileContent:
        repo = self._resolve_repo(repo)
        ref = self._resolve_ref(ref)
        key = f"file:{repo}:{path}:{ref}"
        return await self._cache.get_or_set(key, lambda: self._provider_for(repo).get_file(repo, path, ref))

    async def get_config_history(self, repo: str | None, path: str, limit: int = 20) -> list[CommitInfo]:
        repo = self._resolve_repo(repo)
        key = f"history:{repo}:{path}:{limit}"
        return await self._cache.get_or_set(key, lambda: self._provider_for(repo).get_history(repo, path, limit))

    async def get_commit_diff(self, repo: str | None, sha: str) -> list[FileDiff]:
        repo = self._resolve_repo(repo)
        # A commit's diff is immutable once it exists -- caching it is always safe.
        key = f"diff:{repo}:{sha}"
        return await self._cache.get_or_set(key, lambda: self._provider_for(repo).get_commit_diff(repo, sha))

    async def search_knowledge_base(
        self, query: str, repos: list[str] | None = None, state: str = "all", timeout: float = 10.0
    ) -> list[Issue]:
        target_repos = repos or self._default_repos
        if not target_repos:
            return []

        tasks = {repo: self._provider_for(repo).search_issues(repo, query, state=state) for repo in target_repos}
        results = await gather_with_timeout(tasks, timeout=timeout)

        issues: list[Issue] = []
        for result in results.values():
            if result.status == "ok" and result.data:
                issues.extend(result.data)

        epoch = datetime.min.replace(tzinfo=timezone.utc)
        issues.sort(key=lambda i: i.updated_at or i.created_at or epoch, reverse=True)
        return issues
