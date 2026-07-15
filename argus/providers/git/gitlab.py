"""GitLab provider: file/history/diff/issue access via the REST API v4.

Targets a single self-hosted GitLab instance (base_url), matching how every
other self-hosted-service provider in this codebase works. Read-only.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import ClassVar
from urllib.parse import quote, urlparse

import httpx

from argus.config.settings import GitLabSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.git.exceptions import (
    GitLabNotFoundError,
    GitLabTimeoutError,
    GitLabUnavailableError,
    GitLabUnconfiguredError,
)
from argus.providers.git.models import CommitInfo, Comment, FileContent, FileDiff, Issue, IssueDetail


class GitLabProvider:
    name: ClassVar[str] = "gitlab"

    def __init__(self, settings: GitLabSettings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(self._settings.base_url and self._settings.token)

    @property
    def base_url(self) -> str | None:
        return self._settings.base_url

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self._settings.token or ""}

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        try:
            async with httpx.AsyncClient(timeout=3, headers=self._headers()) as client:
                resp = await client.get(f"{self._settings.base_url}/api/v4/version")
            if resp.status_code < 500:
                return ProviderHealth(name=self.name, status=ProviderStatus.OK)
        except httpx.HTTPError as exc:
            return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE, detail=str(exc))
        return ProviderHealth(name=self.name, status=ProviderStatus.UNAVAILABLE)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise GitLabUnconfiguredError("GitLab is not configured (set GITLAB_BASE_URL and GITLAB_TOKEN).")

    async def get_file(self, repo: str, path: str, ref: str = "HEAD", *, timeout: float = 5.0) -> FileContent:
        self._require_configured()
        project_id = _parse_project_path(repo)
        encoded_path = quote(path, safe="")
        url = f"{self._settings.base_url}/api/v4/projects/{project_id}/repository/files/{encoded_path}"
        payload = await self._get(url, params={"ref": ref}, timeout=timeout, not_found_msg=f"'{path}' in {repo}@{ref}")
        content = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        return FileContent(repo=repo, path=path, ref=ref, content=content, sha=payload.get("blob_id"))

    async def get_history(self, repo: str, path: str, limit: int = 20, *, timeout: float = 5.0) -> list[CommitInfo]:
        self._require_configured()
        project_id = _parse_project_path(repo)
        url = f"{self._settings.base_url}/api/v4/projects/{project_id}/repository/commits"
        payload = await self._get(
            url, params={"path": path, "per_page": limit}, timeout=timeout, not_found_msg=f"'{path}' in {repo}"
        )
        return [_to_commit_info(item) for item in payload]

    async def get_commit_diff(self, repo: str, sha: str, *, timeout: float = 8.0) -> list[FileDiff]:
        self._require_configured()
        project_id = _parse_project_path(repo)
        url = f"{self._settings.base_url}/api/v4/projects/{project_id}/repository/commits/{sha}/diff"
        payload = await self._get(url, timeout=timeout, not_found_msg=f"commit '{sha}' in {repo}")
        return [
            FileDiff(
                path=d.get("new_path") or d.get("old_path", ""),
                patch=d.get("diff"),
                status=_diff_status(d),
            )
            for d in payload
        ]

    async def search_issues(
        self, repo: str, query: str, state: str = "all", limit: int = 20, *, timeout: float = 8.0
    ) -> list[Issue]:
        self._require_configured()
        project_id = _parse_project_path(repo)
        params = {"search": query, "per_page": limit}
        if state != "all":
            params["state"] = state
        url = f"{self._settings.base_url}/api/v4/projects/{project_id}/issues"
        payload = await self._get(url, params=params, timeout=timeout)
        return [_to_issue(repo, item) for item in payload]

    async def get_issue(self, repo: str, issue_id: str, *, timeout: float = 8.0) -> IssueDetail:
        self._require_configured()
        project_id = _parse_project_path(repo)
        base = f"{self._settings.base_url}/api/v4/projects/{project_id}/issues/{issue_id}"
        issue_payload = await self._get(base, timeout=timeout, not_found_msg=f"issue !{issue_id} in {repo}")
        notes_payload = await self._get(f"{base}/notes", timeout=timeout)
        return IssueDetail(
            issue=_to_issue(repo, issue_payload),
            body=issue_payload.get("description") or "",
            comments=[
                Comment(
                    author=(n.get("author") or {}).get("username"),
                    body=n.get("body") or "",
                    created_at=_parse_dt(n.get("created_at")),
                )
                for n in notes_payload
                if not n.get("system")
            ],
        )

    async def _get(self, url: str, *, params: dict | None = None, timeout: float, not_found_msg: str | None = None):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    raise GitLabNotFoundError(f"Not found: {not_found_msg or url}")
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise GitLabTimeoutError(f"Timeout calling GitLab API: {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise GitLabUnavailableError(f"GitLab API error ({exc.response.status_code}): {url}") from exc
        except httpx.HTTPError as exc:
            raise GitLabUnavailableError(f"GitLab unreachable: {exc}") from exc


def _parse_project_path(repo: str) -> str:
    path = urlparse(repo).path if "://" in repo else repo
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    if not path:
        raise ValueError(f"Cannot parse project path from '{repo}'")
    return quote(path, safe="")


def _diff_status(d: dict) -> str:
    if d.get("new_file"):
        return "added"
    if d.get("deleted_file"):
        return "removed"
    if d.get("renamed_file"):
        return "renamed"
    return "modified"


def _to_commit_info(item: dict) -> CommitInfo:
    return CommitInfo(
        sha=item["id"],
        author=item.get("author_name"),
        date=_parse_dt(item.get("authored_date")),
        message=item.get("message", ""),
        url=item.get("web_url"),
    )


def _to_issue(repo: str, item: dict) -> Issue:
    return Issue(
        id=str(item.get("iid", item.get("id", ""))),
        repo=repo,
        title=item.get("title", ""),
        state=item.get("state", "unknown"),
        url=item.get("web_url", ""),
        labels=list(item.get("labels", []) or []),
        created_at=_parse_dt(item.get("created_at")),
        updated_at=_parse_dt(item.get("updated_at")),
        body_excerpt=(item.get("description") or "")[:300] or None,
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
