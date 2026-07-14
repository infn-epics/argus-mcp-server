from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocChunk:
    source_path: str
    text: str


@dataclass
class DocSearchResult:
    source_path: str
    excerpt: str
    score: float
