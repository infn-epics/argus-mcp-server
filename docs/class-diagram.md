# ARGUS Class Diagrams

## Provider hierarchy (EPICS shown; the same shape repeats for every provider)

```mermaid
classDiagram
    class Provider {
        <<protocol>>
        +name: str
        +is_configured() bool
        +health() ProviderHealth
    }

    class EpicsProvider {
        <<protocol>>
        +get(pv_name, timeout) PVValue
        +put(pv_name, value, timeout) PVWriteResult
        +info(pv_name, timeout) PVInfo
        +get_many(pv_names, timeout) list~PVValue~
    }

    class ChannelAccessProvider {
        -settings: EpicsSettings
    }
    class PvAccessProvider {
        -settings: EpicsSettings
    }

    Provider <|.. EpicsProvider
    EpicsProvider <|.. ChannelAccessProvider
    EpicsProvider <|.. PvAccessProvider

    class ArgusError {
        <<exception>>
        +code: str
    }
    class ProviderUnconfiguredError
    class ProviderUnavailableError
    class ProviderTimeoutError
    class EpicsError
    class EpicsUnconfiguredError
    class EpicsConnectionError
    class EpicsTimeoutError
    class PVNotFoundError
    class PVWriteRejectedError

    ArgusError <|-- ProviderUnconfiguredError
    ArgusError <|-- ProviderUnavailableError
    ArgusError <|-- ProviderTimeoutError
    ArgusError <|-- EpicsError
    EpicsError <|-- EpicsUnconfiguredError
    ProviderUnconfiguredError <|-- EpicsUnconfiguredError
    EpicsError <|-- EpicsConnectionError
    ProviderUnavailableError <|-- EpicsConnectionError
    EpicsError <|-- EpicsTimeoutError
    ProviderTimeoutError <|-- EpicsTimeoutError
    EpicsError <|-- PVNotFoundError
    EpicsError <|-- PVWriteRejectedError
```

Every other provider (`ArchiverError`, `ChannelFinderError`,
`KubernetesError`, `ArgoCDError`, `LogbookError`, `ElasticsearchError`,
`DocumentationError`) follows the identical pattern: a root exception per
provider, with `*UnconfiguredError` / `*UnavailableError` / `*TimeoutError`
subclasses wired into `ProviderUnconfiguredError` / `ProviderUnavailableError`
/ `ProviderTimeoutError` so `gather_with_timeout` can classify any provider's
failure uniformly without knowing which provider it was.

## Services and their provider dependencies

```mermaid
classDiagram
    class DeviceService {
        -channelfinder: ChannelFinderProvider
        -cache: AsyncTTLCache
        +resolve_device(name) Device
        +search_devices(query) list~Device~
    }
    class DiagnosticsService {
        -device_service: DeviceService
        -epics: EpicsProvider
        -archiver: ArchiverApplianceProvider
        -kubernetes: KubernetesProvider
        -argocd: ArgoCDProvider
        -logbook: LogbookProvider
        -documentation: LocalTfidfDocumentationProvider
        +device_status(name) DeviceStatusReport
        +diagnose_device(name) DiagnosticReport
    }
    class OperationsService {
        -epics_ca: EpicsProvider
        -epics_pva: EpicsProvider
        -channelfinder: ChannelFinderProvider
        -kubernetes: KubernetesProvider
        -logbook: LogbookProvider
        -procedures: ProcedureRegistry
        +get_pv(name) PVValue
        +set_pv(name, value) PVWriteResult
        +search_pvs(query) list~CFChannel~
        +list_iocs(namespace) list~PodStatus~
        +restart_ioc(pod, ns) bool
        +machine_summary(namespace) MachineSummary
        +execute_procedure(name, params) dict
    }
    class HistoryService {
        -archiver: ArchiverApplianceProvider
        -logbook: LogbookProvider
        -elastic: ElasticsearchProvider
        +get_history(pv, start, end) ArchiverSeries
        +get_alarm_history(device) list~LogbookEntry~
        +get_logs(query) list~LogRecord~
    }
    class DocumentationService {
        -documentation: LocalTfidfDocumentationProvider
        +search_documentation(query, device) list~DocSearchResult~
    }

    DiagnosticsService --> DeviceService
```

## Core domain models

```mermaid
classDiagram
    class Device {
        +name: str
        +device_class: str?
        +pv_names: list~str~
        +primary_pv: str?
        +ioc_name: str?
        +pod_name: str?
        +namespace: str?
        +argocd_app: str?
        +git_repo: str?
        +rack: str?
        +owner: str?
        +documentation_refs: list~str~
        +tags: list~str~
        +properties: dict
    }
    class ProviderResult~T~ {
        +provider: str
        +status: ok|unconfigured|unavailable|timeout|error|skipped
        +data: T?
        +error: str?
        +latency_ms: float?
    }
    class DiagnosticReport {
        +device: Device
        +live_pvs: ProviderResult
        +history: ProviderResult
        +pod: ProviderResult
        +pod_logs: ProviderResult
        +argocd: ProviderResult
        +logbook: ProviderResult
        +documentation: ProviderResult
        +degraded_providers: list~str~
    }
    class DeviceStatusReport {
        +device: Device
        +live_pvs: ProviderResult
        +pod: ProviderResult
        +degraded_providers: list~str~
    }

    DiagnosticReport --> Device
    DiagnosticReport --> ProviderResult
    DeviceStatusReport --> Device
    DeviceStatusReport --> ProviderResult
```
