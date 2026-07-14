"""Default DocumentationProvider: local TF-IDF search over a docs folder.

No external service, no model download — honest about "don't over-engineer"
for a first pass. The DocumentationProvider protocol keeps a real
embedding/vector-DB backend a drop-in future replacement.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import ClassVar

from argus.config.settings import DocumentationSettings
from argus.providers.base import ProviderHealth, ProviderStatus
from argus.providers.documentation.exceptions import DocumentationIndexError, DocumentationUnconfiguredError
from argus.providers.documentation.models import DocChunk, DocSearchResult

_DOC_EXTENSIONS = {".md", ".txt", ".rst"}
_CHUNK_SIZE_CHARS = 1000


class LocalTfidfDocumentationProvider:
    name: ClassVar[str] = "documentation"

    def __init__(self, settings: DocumentationSettings) -> None:
        self._settings = settings
        self._vectorizer = None
        self._matrix = None
        self._chunks: list[DocChunk] = []
        self._indexed = False

    def is_configured(self) -> bool:
        return bool(self._settings.docs_path) and Path(self._settings.docs_path).is_dir()

    async def health(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(name=self.name, status=ProviderStatus.UNCONFIGURED)
        return ProviderHealth(name=self.name, status=ProviderStatus.OK)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise DocumentationUnconfiguredError(
                "Documentation search is not configured (set DOCS_PATH to a folder of docs)."
            )

    def reindex(self) -> None:
        self._require_configured()
        from sklearn.feature_extraction.text import TfidfVectorizer

        chunks = list(_load_chunks(Path(self._settings.docs_path)))
        if not chunks:
            self._chunks, self._vectorizer, self._matrix = [], None, None
            self._indexed = True
            return

        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            matrix = vectorizer.fit_transform([c.text for c in chunks])
        except ValueError as exc:
            raise DocumentationIndexError(f"Failed to build documentation index: {exc}") from exc

        self._chunks = chunks
        self._vectorizer = vectorizer
        self._matrix = matrix
        self._indexed = True

        if self._settings.index_path:
            try:
                with open(self._settings.index_path, "wb") as fh:
                    pickle.dump((self._chunks, self._vectorizer, self._matrix), fh)
            except OSError:
                pass  # persistence is a nice-to-have, not required for correctness

    def _ensure_index(self) -> None:
        if self._indexed:
            return
        if self._settings.index_path and Path(self._settings.index_path).exists():
            try:
                with open(self._settings.index_path, "rb") as fh:
                    self._chunks, self._vectorizer, self._matrix = pickle.load(fh)
                self._indexed = True
                return
            except (OSError, pickle.PickleError):
                pass
        self.reindex()

    async def search(self, query: str, top_k: int = 5) -> list[DocSearchResult]:
        self._require_configured()
        self._ensure_index()

        if not self._chunks or self._vectorizer is None:
            return []

        from sklearn.metrics.pairwise import cosine_similarity

        query_vector = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self._matrix)[0]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        return [
            DocSearchResult(
                source_path=self._chunks[i].source_path,
                excerpt=self._chunks[i].text[:400],
                score=float(scores[i]),
            )
            for i in ranked
            if scores[i] > 0
        ]


def _load_chunks(docs_path: Path):
    for path in sorted(docs_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _DOC_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for start in range(0, len(text), _CHUNK_SIZE_CHARS):
            chunk_text = text[start : start + _CHUNK_SIZE_CHARS].strip()
            if chunk_text:
                yield DocChunk(source_path=str(path.relative_to(docs_path)), text=chunk_text)
