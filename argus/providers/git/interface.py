"""Common protocol implemented by both the GitHub and GitLab adapters.

KnowledgeService depends on this Protocol, not on either concrete adapter,
and picks the right one per call based on the host in a repo URL (same
pattern OperationsService uses to pick Channel Access vs pvAccess per PV).
"""

from __future__ import annotations

from typing import Protocol

from argus.providers.base import Provider
from argus.providers.git.models import CommitInfo, FileContent, FileDiff, Issue, IssueDetail


class GitProvider(Provider, Protocol):
    async def get_file(self, repo: str, path: str, ref: str = "HEAD") -> FileContent: ...

    async def get_history(self, repo: str, path: str, limit: int = 20) -> list[CommitInfo]: ...

    async def get_commit_diff(self, repo: str, sha: str) -> list[FileDiff]: ...

    async def search_issues(
        self, repo: str, query: str, state: str = "all", limit: int = 20
    ) -> list[Issue]: ...

    async def get_issue(self, repo: str, issue_id: str) -> IssueDetail: ...
