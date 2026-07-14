from __future__ import annotations

from argus.core.errors import ArgusError, ProviderUnavailableError, ProviderUnconfiguredError


class DocumentationError(ArgusError):
    code = "documentation_error"


class DocumentationUnconfiguredError(DocumentationError, ProviderUnconfiguredError):
    code = "documentation_unconfigured"


class DocumentationUnavailableError(DocumentationError, ProviderUnavailableError):
    code = "documentation_unavailable"


class DocumentationIndexError(DocumentationError):
    code = "documentation_index_error"
