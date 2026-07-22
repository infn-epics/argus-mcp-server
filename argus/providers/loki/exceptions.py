from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class LokiError(ArgusError):
    code = "loki_error"


class LokiUnconfiguredError(LokiError, ProviderUnconfiguredError):
    code = "loki_unconfigured"


class LokiUnavailableError(LokiError, ProviderUnavailableError):
    code = "loki_unavailable"


class LokiTimeoutError(LokiError, ProviderTimeoutError):
    code = "loki_timeout"


class LokiQueryError(LokiError):
    code = "loki_query_error"
