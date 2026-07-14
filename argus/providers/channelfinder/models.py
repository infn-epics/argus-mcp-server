from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CFChannel:
    name: str
    owner: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
