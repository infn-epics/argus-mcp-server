from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LokiLogEntry:
    timestamp: datetime
    namespace: str
    pod: str
    container: str
    line: str
