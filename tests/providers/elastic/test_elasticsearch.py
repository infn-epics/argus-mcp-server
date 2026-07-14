import pytest

from argus.config.settings import ElasticSettings
from argus.providers.elastic.elasticsearch import ElasticsearchProvider
from argus.providers.elastic.exceptions import ElasticsearchQueryError, ElasticsearchUnconfiguredError


async def test_unconfigured_raises_clean_error():
    provider = ElasticsearchProvider(ElasticSettings(_env_file=None))
    with pytest.raises(ElasticsearchUnconfiguredError):
        await provider.search_logs(query="error")


class _FakeAsyncElasticsearchClient:
    def __init__(self, hits):
        self._hits = hits

    async def search(self, index, body, request_timeout):
        return {"hits": {"hits": self._hits}}


async def test_search_logs_parses_hits():
    provider = ElasticsearchProvider(ElasticSettings(_env_file=None, ELASTIC_URL="http://es.test:9200"))
    provider._client = _FakeAsyncElasticsearchClient(
        hits=[{"_source": {"@timestamp": "2026-01-01T00:00:00", "message": "IOC restarted", "level": "INFO"}}]
    )

    records = await provider.search_logs(query="restarted")
    assert records[0].message == "IOC restarted"
    assert records[0].level == "INFO"


async def test_search_logs_unexpected_shape_raises_query_error():
    provider = ElasticsearchProvider(ElasticSettings(_env_file=None, ELASTIC_URL="http://es.test:9200"))

    class _BrokenClient:
        async def search(self, index, body, request_timeout):
            return {"unexpected": "shape"}

    provider._client = _BrokenClient()
    with pytest.raises(ElasticsearchQueryError):
        await provider.search_logs(query="restarted")
