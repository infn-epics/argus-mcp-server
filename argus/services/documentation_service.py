from __future__ import annotations

from argus.providers.documentation.models import DocSearchResult
from argus.providers.documentation.rag import LocalTfidfDocumentationProvider


class DocumentationService:
    def __init__(self, documentation: LocalTfidfDocumentationProvider) -> None:
        self._documentation = documentation

    async def search_documentation(
        self, query: str, device: str | None = None, top_k: int = 5
    ) -> list[DocSearchResult]:
        enriched_query = f"{device} {query}" if device else query
        return await self._documentation.search(enriched_query, top_k=top_k)
