from __future__ import annotations

from argus.core.errors import ArgusError, ProviderUnavailableError, ProviderUnconfiguredError


class KubernetesError(ArgusError):
    code = "kubernetes_error"


class KubernetesUnconfiguredError(KubernetesError, ProviderUnconfiguredError):
    code = "kubernetes_unconfigured"


class KubernetesUnavailableError(KubernetesError, ProviderUnavailableError):
    code = "kubernetes_unavailable"


class KubernetesResourceNotFoundError(KubernetesError):
    code = "kubernetes_resource_not_found"
