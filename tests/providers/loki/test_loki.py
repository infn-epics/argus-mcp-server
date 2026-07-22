import httpx
import pytest
import respx

from argus.config.settings import LokiSettings
from argus.providers.loki.exceptions import LokiQueryError, LokiUnconfiguredError
from argus.providers.loki.loki import LokiProvider


def _configured() -> LokiProvider:
    return LokiProvider(LokiSettings(_env_file=None, LOKI_BASE_URL="http://loki.test"))


async def test_unconfigured_raises_clean_error():
    provider = LokiProvider(LokiSettings(_env_file=None))
    with pytest.raises(LokiUnconfiguredError):
        await provider.search(namespace="btf")


@respx.mock
async def test_search_parses_streams_sorted_newest_first():
    provider = _configured()
    respx.get("http://loki.test/loki/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [
                        {
                            "stream": {"namespace": "btf", "pod": "ioc-qf12-abc", "container": "ioc"},
                            "values": [
                                ["1700000000000000000", "older line"],
                                ["1700000002000000000", "newer line"],
                            ],
                        }
                    ],
                },
            },
        )
    )
    entries = await provider.search(namespace="btf", pod="ioc-qf12-abc")
    assert [e.line for e in entries] == ["newer line", "older line"]
    assert entries[0].namespace == "btf"
    assert entries[0].container == "ioc"


@respx.mock
async def test_search_builds_query_with_label_matchers_and_text_filter():
    provider = _configured()
    route = respx.get("http://loki.test/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"status": "success", "data": {"resultType": "streams", "result": []}})
    )
    await provider.search(namespace="btf", pod="ioc-qf12", container="ioc", query="error")

    sent_query = dict(httpx.QueryParams(route.calls.last.request.url.query))["query"]
    assert sent_query == '{namespace="btf", pod="ioc-qf12", container="ioc"} |= "error"'


@respx.mock
async def test_search_with_no_filters_matches_all_namespaces():
    provider = _configured()
    route = respx.get("http://loki.test/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"status": "success", "data": {"resultType": "streams", "result": []}})
    )
    await provider.search()

    sent_query = dict(httpx.QueryParams(route.calls.last.request.url.query))["query"]
    assert sent_query == '{namespace=~".+"}'


@respx.mock
async def test_search_unexpected_shape_raises_query_error():
    provider = _configured()
    respx.get("http://loki.test/loki/api/v1/query_range").mock(return_value=httpx.Response(200, json={"unexpected": "shape"}))
    with pytest.raises(LokiQueryError):
        await provider.search(namespace="btf")


@respx.mock
async def test_search_text_filter_is_safely_quoted():
    provider = _configured()
    route = respx.get("http://loki.test/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"status": "success", "data": {"resultType": "streams", "result": []}})
    )
    # A crafted query value containing a quote must not be able to break out
    # of its string literal and inject an extra label matcher.
    await provider.search(namespace="btf", query='"} or {namespace="other')

    sent_query = dict(httpx.QueryParams(route.calls.last.request.url.query))["query"]
    assert sent_query == '{namespace="btf"} |= "\\"} or {namespace=\\"other"'
