from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class DocumentationError(ArgusError):
    code = "documentation_error"


class DocumentationUnconfiguredError(DocumentationError, ProviderUnconfiguredError):
    code = "documentation_unconfigured"


class DocumentationUnavailableError(DocumentationError, ProviderUnavailableError):
    code = "documentation_unavailable"


class DocumentationTimeoutError(DocumentationError, ProviderTimeoutError):
    code = "documentation_timeout"


class DocumentationIndexError(DocumentationError):
    code = "documentation_index_error"


class DocumentationQueryError(DocumentationError):
    code = "documentation_query_error"
