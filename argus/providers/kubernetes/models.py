from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PodStatus:
    name: str
    namespace: str
    phase: str
    ready: bool
    restart_count: int
    node: str | None = None
    started_at: datetime | None = None
