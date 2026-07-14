from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArchiverSample:
    timestamp: datetime
    value: float
    severity: int | None = None


@dataclass
class ArchiverSeries:
    pv_name: str
    samples: list[ArchiverSample] = field(default_factory=list)
