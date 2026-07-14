"""Base error hierarchy shared by every provider and service.

Each provider module defines its own subclasses rooted here (e.g. ``EpicsError``),
so the tool dispatch layer can catch one common type (``ArgusError``) while still
letting callers distinguish provider-specific failures when they want to.
"""

from __future__ import annotations


class ArgusError(Exception):
    """Base for all ARGUS errors. Carries a machine-readable ``code``."""

    code: str = "argus_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ProviderUnconfiguredError(ArgusError):
    """Raised when a provider is called but has no configuration set."""

    code = "provider_unconfigured"


class ProviderUnavailableError(ArgusError):
    """Raised when a provider is configured but the backend is unreachable."""

    code = "provider_unavailable"


class ProviderTimeoutError(ArgusError):
    """Raised when a provider call exceeds its allotted timeout."""

    code = "provider_timeout"


class ValidationError(ArgusError):
    """Raised when tool/service input fails validation before reaching a provider."""

    code = "validation_error"
