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


@respx.mock
async def test_application_error_with_http_200_raises_query_error():
    # RAGFLOW returns HTTP 200 even for application-level errors, with no
    # "data" key at all -- confirmed live: {"code": 102, "message":
    # "`dataset_ids` is required."} This must not surface as a generic
    # KeyError-derived message; the real RAGFLOW message should come through.
    provider = _configured()
    respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"code": 102, "message": "`dataset_ids` is required."})
    )
    with pytest.raises(DocumentationQueryError, match="dataset_ids"):
        await provider.search("quadrupole")


@respx.mock
async def test_dataset_names_resolved_to_ids_via_datasets_listing():
    provider = RagflowDocumentationProvider(
        RagflowSettings(
            _env_file=None,
            RAGFLOW_BASE_URL="http://ragflow.test",
            RAGFLOW_API_KEY="secret",
            RAGFLOW_DATASET_NAMES="Controlli, BTF",
        )
    )
    respx.get("http://ragflow.test/api/v1/datasets").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": [
                    {"id": "id-controlli", "name": "Controlli-KB"},
                    {"id": "id-sparc", "name": "CONFLUENCE-SPARC"},
                ],
            },
        )
    )
    route = respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"chunks": []}})
    )
    await provider.search("quadrupole")

    import json

    body = json.loads(route.calls.last.request.content)
    # "Controlli" matched (substring of "Controlli-KB"); "BTF" matched no
    # dataset name and is silently skipped, not an error.
    assert body["dataset_ids"] == ["id-controlli"]


@respx.mock
async def test_dataset_names_listing_only_fetched_once_per_cache_window():
    provider = RagflowDocumentationProvider(
        RagflowSettings(
            _env_file=None,
            RAGFLOW_BASE_URL="http://ragflow.test",
            RAGFLOW_API_KEY="secret",
            RAGFLOW_DATASET_NAMES="Controlli",
        )
    )
    datasets_route = respx.get("http://ragflow.test/api/v1/datasets").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": [{"id": "id-controlli", "name": "Controlli-KB"}]})
    )
    respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"chunks": []}})
    )
    await provider.search("quadrupole")
    await provider.search("dipole")
    assert datasets_route.call_count == 1


@respx.mock
async def test_dataset_ids_and_dataset_names_combine():
    provider = RagflowDocumentationProvider(
        RagflowSettings(
            _env_file=None,
            RAGFLOW_BASE_URL="http://ragflow.test",
            RAGFLOW_API_KEY="secret",
            RAGFLOW_DATASET_IDS="explicit-id",
            RAGFLOW_DATASET_NAMES="Controlli",
        )
    )
    respx.get("http://ragflow.test/api/v1/datasets").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": [{"id": "id-controlli", "name": "Controlli-KB"}]})
    )
    route = respx.post("http://ragflow.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"chunks": []}})
    )
    await provider.search("quadrupole")

    import json

    body = json.loads(route.calls.last.request.content)
    assert body["dataset_ids"] == ["explicit-id", "id-controlli"]
