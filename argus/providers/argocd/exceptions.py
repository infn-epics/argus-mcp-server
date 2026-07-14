from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class ArgoCDError(ArgusError):
    code = "argocd_error"


class ArgoCDUnconfiguredError(ArgoCDError, ProviderUnconfiguredError):
    code = "argocd_unconfigured"


class ArgoCDUnavailableError(ArgoCDError, ProviderUnavailableError):
    code = "argocd_unavailable"


class ArgoCDTimeoutError(ArgoCDError, ProviderTimeoutError):
    code = "argocd_timeout"


class ArgoCDAuthError(ArgoCDError):
    code = "argocd_auth_error"
