from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class EpicsError(ArgusError):
    code = "epics_error"


class EpicsUnconfiguredError(EpicsError, ProviderUnconfiguredError):
    code = "epics_unconfigured"


class EpicsConnectionError(EpicsError, ProviderUnavailableError):
    code = "epics_connection_error"


class EpicsTimeoutError(EpicsError, ProviderTimeoutError):
    code = "epics_timeout"


class PVNotFoundError(EpicsError):
    code = "pv_not_found"


class PVWriteRejectedError(EpicsError):
    code = "pv_write_rejected"
