from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class ChannelFinderError(ArgusError):
    code = "channelfinder_error"


class ChannelFinderUnconfiguredError(ChannelFinderError, ProviderUnconfiguredError):
    code = "channelfinder_unconfigured"


class ChannelFinderUnavailableError(ChannelFinderError, ProviderUnavailableError):
    code = "channelfinder_unavailable"


class ChannelFinderTimeoutError(ChannelFinderError, ProviderTimeoutError):
    code = "channelfinder_timeout"


class ChannelFinderQueryError(ChannelFinderError):
    code = "channelfinder_query_error"
