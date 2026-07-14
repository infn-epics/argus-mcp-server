from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class ElasticsearchError(ArgusError):
    code = "elasticsearch_error"


class ElasticsearchUnconfiguredError(ElasticsearchError, ProviderUnconfiguredError):
    code = "elasticsearch_unconfigured"


class ElasticsearchUnavailableError(ElasticsearchError, ProviderUnavailableError):
    code = "elasticsearch_unavailable"


class ElasticsearchTimeoutError(ElasticsearchError, ProviderTimeoutError):
    code = "elasticsearch_timeout"


class ElasticsearchQueryError(ElasticsearchError):
    code = "elasticsearch_query_error"
