import pytest

from argus.config.settings import DocumentationSettings
from argus.providers.documentation.exceptions import DocumentationUnconfiguredError
from argus.providers.documentation.rag import LocalTfidfDocumentationProvider


async def test_unconfigured_raises_clean_error():
    provider = LocalTfidfDocumentationProvider(DocumentationSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(DocumentationUnconfiguredError):
        await provider.search("quadrupole")


async def test_search_finds_relevant_chunk(tmp_path):
    (tmp_path / "quadrupole.md").write_text(
        "The QF12 quadrupole magnet focuses the beam horizontally. "
        "Maximum current is 150 amps and it is powered by PS-QF12."
    )
    (tmp_path / "vacuum.md").write_text(
        "The vacuum system maintains ultra-high vacuum in the beam pipe using ion pumps."
    )

    provider = LocalTfidfDocumentationProvider(
        DocumentationSettings(_env_file=None, DOCS_PATH=str(tmp_path))
    )
    assert provider.is_configured() is True

    results = await provider.search("quadrupole magnet current", top_k=2)
    assert results
    assert "quadrupole" in results[0].source_path


async def test_search_with_no_matching_docs_returns_empty(tmp_path):
    (tmp_path / "vacuum.md").write_text("Ion pumps maintain vacuum.")
    provider = LocalTfidfDocumentationProvider(DocumentationSettings(_env_file=None, DOCS_PATH=str(tmp_path)))
    results = await provider.search("zzz_completely_unrelated_term_zzz")
    assert results == []
