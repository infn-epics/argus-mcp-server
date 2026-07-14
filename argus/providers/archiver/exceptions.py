from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class ArchiverError(ArgusError):
    code = "archiver_error"


class ArchiverUnconfiguredError(ArchiverError, ProviderUnconfiguredError):
    code = "archiver_unconfigured"


class ArchiverUnavailableError(ArchiverError, ProviderUnavailableError):
    code = "archiver_unavailable"


class ArchiverTimeoutError(ArchiverError, ProviderTimeoutError):
    code = "archiver_timeout"


class ArchiverQueryError(ArchiverError):
    code = "archiver_query_error"
