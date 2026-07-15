"""GitHub provider: file/history/diff/issue access via the REST API v3.

Read-only. Issue search delegates to GitHub's own search API rather than
ARGUS reimplementing full-text search.
"""

from __future__ import annotations

import base64
from typing import ClassVar
from urllib.parse import urlparse

import httpx

from argus.config.settings import GitHubSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.git.exceptions import (
    GitHubNotFoundError,
    GitHubTimeoutError,
    GitHubUnavailableError,
    GitHubUnconfiguredError,
)
from argus.providers.git.models import CommitInfo, Comment, FileContent, FileDiff, Issue, IssueDetail


class GitHubProvider:
    name: ClassVar[str] = "github"

    def __init__(self, settings: GitHubSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3, headers=self._headers()) as client:
                resp = await client.get(f"{self._settings.base_url}/rate_limit")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise GitHubUnconfiguredError("GitHub is not configured (set GITHUB_TOKEN).")

    async def get_file(self, repo: str, path: str, ref: str = "HEAD", *, timeout: float = 5.0) -> FileContent:
        self._require_configured()
        owner, name = _parse_owner_repo(repo)
        params = {} if ref in (None, "HEAD") else {"ref": ref}
        url = f"{self._settings.base_url}/repos/{owner}/{name}/contents/{path}"
        payload = await self._get(url, params=params, timeout=timeout, not_found_msg=f"'{path}' in {repo}@{ref}")
        content = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        return FileContent(repo=repo, path=path, ref=ref, content=content, sha=payload.get("sha"))

    async def get_history(self, repo: str, path: str, limit: int = 20, *, timeout: float = 5.0) -> list[CommitInfo]:
        self._require_configured()
        owner, name = _parse_owner_repo(repo)
        url = f"{self._settings.base_url}/repos/{owner}/{name}/commits"
        payload = await self._get(
            url, params={"path": path, "per_page": limit}, timeout=timeout, not_found_msg=f"'{path}' in {repo}"
        )
        return [_to_commit_info(item) for item in payload]

    async def get_commit_diff(self, repo: str, sha: str, *, timeout: float = 8.0) -> list[FileDiff]:
        self._require_configured()
        owner, name = _parse_owner_repo(repo)
        url = f"{self._settings.base_url}/repos/{owner}/{name}/commits/{sha}"
        payload = await self._get(url, timeout=timeout, not_found_msg=f"commit '{sha}' in {repo}")
        return [
            FileDiff(
                path=f["filename"],
                patch=f.get("patch"),
                additions=f.get("additions"),
                deletions=f.get("deletions"),
                status=f.get("status"),
            )
            for f in payload.get("files", [])
        ]

    async def search_issues(
        self, repo: str, query: str, state: str = "all", limit: int = 20, *, timeout: float = 8.0
    ) -> list[Issue]:
        self._require_configured()
        owner, name = _parse_owner_repo(repo)
        q = f"{query} repo:{owner}/{name}"
        if state != "all":
            q += f" state:{state}"
        url = f"{self._settings.base_url}/search/issues"
        payload = await self._get(url, params={"q": q, "per_page": limit}, timeout=timeout)
        return [_to_issue(repo, item) for item in payload.get("items", [])]

    async def get_issue(self, repo: str, issue_id: str, *, timeout: float = 8.0) -> IssueDetail:
        self._require_configured()
        owner, name = _parse_owner_repo(repo)
        base = f"{self._settings.base_url}/repos/{owner}/{name}/issues/{issue_id}"
        issue_payload = await self._get(base, timeout=timeout, not_found_msg=f"issue #{issue_id} in {repo}")
        comments_payload = await self._get(f"{base}/comments", timeout=timeout)
        return IssueDetail(
            issue=_to_issue(repo, issue_payload),
            body=issue_payload.get("body") or "",
            comments=[
                Comment(author=(c.get("user") or {}).get("login"), body=c.get("body") or "", created_at=_parse_dt(c.get("created_at")))
                for c in comments_payload
            ],
        )

    async def _get(self, url: str, *, params: dict | None = None, timeout: float, not_found_msg: str | None = None):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    raise GitHubNotFoundError(f"Not found: {not_found_msg or url}")
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise GitHubTimeoutError(f"Timeout calling GitHub API: {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise GitHubUnavailableError(f"GitHub API error ({exc.response.status_code}): {url}") from exc
        except httpx.HTTPError as exc:
            raise GitHubUnavailableError(f"GitHub unreachable: {exc}") from exc


def _parse_owner_repo(repo: str) -> tuple[str, str]:
    path = urlparse(repo).path if "://" in repo else repo
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from '{repo}'")
    owner, name = parts[-2], parts[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return owner, name


def _to_commit_info(item: dict) -> CommitInfo:
    commit = item.get("commit", {})
    author = commit.get("author", {})
    return CommitInfo(
        sha=item["sha"],
        author=author.get("name"),
        date=_parse_dt(author.get("date")),
        message=commit.get("message", ""),
        url=item.get("html_url"),
    )


def _to_issue(repo: str, item: dict) -> Issue:
    return Issue(
        id=str(item.get("number", item.get("id", ""))),
        repo=repo,
        title=item.get("title", ""),
        state=item.get("state", "unknown"),
        url=item.get("html_url", ""),
        labels=[label.get("name", "") if isinstance(label, dict) else str(label) for label in item.get("labels", [])],
        created_at=_parse_dt(item.get("created_at")),
        updated_at=_parse_dt(item.get("updated_at")),
        body_excerpt=(item.get("body") or "")[:300] or None,
    )


def _parse_dt(value: str | None):
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
