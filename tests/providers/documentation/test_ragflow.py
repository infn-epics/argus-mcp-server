import httpx
import pytest
import respx

from argus.config.settings import RagflowSettings
from argus.providers.documentation.exceptions import (
    DocumentationQueryError,
    DocumentationTimeoutError,
    DocumentationUnavailableError,
    DocumentationUnconfiguredError,
)
from argus.providers.documentation.ragflow import RagflowDocumentationProvider


def _configured() -> RagflowDocumentationProvider:
    return RagflowDocumentationProvider(
        RagflowSettings(_env_file=None, RAGFLOW_BASE_URL="http://ragflow.test", RAGFLOW_API_KEY="secret")
    )


async def test_unconfigured_raises_clean_error():
    provider = RagflowDocumentationProvider(RagflowSettings(_env_file=None))
    assert provider.is_configured() is False
    with pytest.raises(DocumentationUnconfiguredError):
        await provider.search("quadrupole")


@respx.mock
async def test_search_parses_chunks_into_results():
    provider = _configured()
    respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "chunks": [
                        {
                            "document_keyword": "quadrupole.md",
                            "content": "The QF12 quadrupole magnet focuses the beam horizontally.",
                            "similarity": 0.87,
                        }
                    ]
                }
            },
        )
    )
    results = await provider.search("quadrupole magnet")
    assert results[0].source_path == "quadrupole.md"
    assert "QF12" in results[0].excerpt
    assert results[0].score == pytest.approx(0.87)


@respx.mock
async def test_search_sends_dataset_ids_when_configured():
    provider = RagflowDocumentationProvider(
        RagflowSettings(
            _env_file=None,
            RAGFLOW_BASE_URL="http://ragflow.test",
            RAGFLOW_API_KEY="secret",
            RAGFLOW_DATASET_IDS="ds1, ds2",
        )
    )
    route = respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"data": {"chunks": []}})
    )
    await provider.search("quadrupole")
    assert route.calls.last.request.content
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["dataset_ids"] == ["ds1", "ds2"]


@respx.mock
async def test_unreachable_backend_raises_unavailable():
    provider = _configured()
    respx.post("http://ragflow.test/api/v1/retrieval").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(DocumentationUnavailableError):
        await provider.search("quadrupole")


@respx.mock
async def test_unexpected_response_shape_raises_query_error():
    provider = _configured()
    respx.post("http://ragflow.test/api/v1/retrieval").mock(return_value=httpx.Response(200, json={"data": {}}))
    with pytest.raises(DocumentationQueryError):
        await provider.search("quadrupole")


def test_default_timeout_is_20_seconds():
    provider = _configured()
    assert provider._settings.timeout_seconds == 20.0


@respx.mock
async def test_slow_backend_raises_timeout_error():
    provider = _configured()
    respx.post("http://ragflow.test/api/v1/retrieval").mock(side_effect=httpx.TimeoutException("timed out"))
    with pytest.raises(DocumentationTimeoutError):
        await provider.search("quadrupole")


@respx.mock
async def test_timeout_configurable_via_settings():
    provider = RagflowDocumentationProvider(
        RagflowSettings(
            _env_file=None,
            RAGFLOW_BASE_URL="http://ragflow.test",
            RAGFLOW_API_KEY="secret",
            RAGFLOW_TIMEOUT_SECONDS=5,
        )
    )
    assert provider._settings.timeout_seconds == 5
    respx.post("http://ragflow.test/api/v1/retrieval").mock(return_value=httpx.Response(200, json={"data": {"chunks": []}}))
    await provider.search("quadrupole")
