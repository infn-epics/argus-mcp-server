# ADR 0003: Local TF-IDF as the default documentation search backend

## Status

Accepted.

## Context

`search_documentation()` needs to search technical manuals/documentation.
The obvious modern approach is embeddings + a vector DB. But the spec is
explicit: "do not over-engineer" and prefer readability over cleverness, and
this pass is meant to give a working default with zero required external
services — most sites won't have a vector DB running on day one.

## Decision

`providers/documentation/interface.py` defines a `DocumentationProvider`
protocol (`search()`, `reindex()`). The default implementation,
`LocalTfidfDocumentationProvider` (`rag.py`), walks a docs folder
(`DOCS_PATH`), chunks files, and builds a `scikit-learn` `TfidfVectorizer`
index, optionally persisted to disk (`DOCS_INDEX_PATH`). Search is cosine
similarity over TF-IDF vectors — no model download, no GPU, no external
service, instant startup.

## Consequences

- Works out of the box the moment `DOCS_PATH` points at a folder of
  `.md`/`.txt`/`.rst` files.
- Search quality is keyword/term-overlap based, not semantic — it won't
  understand paraphrases or synonyms the way embeddings would.
- Because the concrete implementation lives behind the
  `DocumentationProvider` protocol, a future
  `SentenceTransformerDocumentationProvider` or a real vector-DB adapter can
  be swapped in via `AppContext.build()` alone — `documentation_service.py`
  and the `search_documentation` tool never need to change.
