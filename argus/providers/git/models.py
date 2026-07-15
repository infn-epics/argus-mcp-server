from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FileContent:
    repo: str
    path: str
    ref: str
    content: str
    sha: str | None = None


@dataclass
class CommitInfo:
    sha: str
    author: str | None
    date: datetime | None
    message: str
    url: str | None = None


@dataclass
class FileDiff:
    path: str
    patch: str | None = None
    additions: int | None = None
    deletions: int | None = None
    status: str | None = None  # added | modified | removed | renamed


@dataclass
class Issue:
    id: str
    repo: str
    title: str
    state: str
    url: str
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    body_excerpt: str | None = None


@dataclass
class Comment:
    author: str | None
    body: str
    created_at: datetime | None = None


@dataclass
class IssueDetail:
    issue: Issue
    body: str
    comments: list[Comment] = field(default_factory=list)
