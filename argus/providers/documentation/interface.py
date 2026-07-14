"""DocumentationProvider protocol — kept separate from the default TF-IDF
implementation so a real vector-DB-backed provider can be swapped in later
without touching documentation_service.py.
"""

from __future__ import annotations

from typing import Protocol

from argus.providers.base import Provider
from argus.providers.documentation.models import DocSearchResult


class DocumentationProvider(Provider, Protocol):
    async def search(self, query: str, top_k: int = 5) -> list[DocSearchResult]: ...

    def reindex(self) -> None: ...
