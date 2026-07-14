from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogRecord:
    timestamp: datetime | None
    source: str | None
    message: str
    level: str | None = None
    raw: dict = field(default_factory=dict)
