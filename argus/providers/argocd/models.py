from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArgoApplicationStatus:
    name: str
    sync_status: str
    health_status: str
    revision: str | None = None
    repo_url: str | None = None
    last_sync_at: str | None = None
