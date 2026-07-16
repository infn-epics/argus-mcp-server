from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SnrNode:
    unique_id: str
    name: str
    node_type: str  # "FOLDER" | "CONFIGURATION" | "SNAPSHOT"
    description: str | None = None
    created: datetime | None = None
    last_modified: datetime | None = None
    user_name: str | None = None


@dataclass
class SnrPvEntry:
    pv_name: str
    readback_pv_name: str | None = None
    read_only: bool = False


@dataclass
class SnrConfiguration:
    unique_id: str
    pv_list: list[SnrPvEntry] = field(default_factory=list)


@dataclass
class SnrSnapshotValue:
    pv_name: str
    value: object
    readback_value: object = None
    units: str | None = None
    severity: str | None = None


@dataclass
class SnrSnapshot:
    unique_id: str
    items: list[SnrSnapshotValue] = field(default_factory=list)
