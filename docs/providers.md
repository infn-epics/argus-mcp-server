# Provider Reference

Every provider follows the same contract (`argus/providers/base.py`):

```python
class Provider(Protocol):
    name: ClassVar[str]
    def is_configured(self) -> bool: ...
    async def health(self) -> ProviderHealth: ...
```

`is_configured()` is cheap and side-effect free (no I/O) so `AppContext.build()`
can construct every provider unconditionally at startup. Calling a domain
method on an unconfigured provider raises that provider's
`*UnconfiguredError`, which the service layer turns into
`ProviderResult(status="unconfigured")` rather than a crash — this is what
"unconfigured" looks like from an MCP tool response:

```json
{
  "status": "error",
  "code": "channelfinder_unconfigured",
  "message": "ChannelFinder is not configured (set CHANNELFINDER_BASE_URL)."
}
```

(or, inside a `diagnose_device()` report, that same section reports
`"status": "unconfigured"` instead of failing the whole call.)

| Provider | Module | Backing library/API | Key env vars | Exceptions |
|---|---|---|---|---|
| Channel Access | `providers/epics/channel_access.py` | [`aioca`](https://pypi.org/project/aioca/) (async-native CA client) | `EPICS_CA_ADDR_LIST`, `EPICS_CA_AUTO_ADDR_LIST` | `EpicsConnectionError`, `EpicsTimeoutError`, `PVWriteRejectedError` |
| pvAccess | `providers/epics/pvaccess.py` | [`p4p`](https://pypi.org/project/p4p/) asyncio client | `EPICS_PVA_ADDR_LIST` | same `Epics*` hierarchy |
| Archiver Appliance | `providers/archiver/archiver_appliance.py` | REST: `/retrieval/data/getData.json` | `ARCHIVER_BASE_URL` | `ArchiverUnavailableError`, `ArchiverQueryError`, `ArchiverTimeoutError` |
| ChannelFinder | `providers/channelfinder/channelfinder.py` | REST: `/ChannelFinder/resources/channels` | `CHANNELFINDER_BASE_URL`, `CHANNELFINDER_USERNAME`/`PASSWORD` | `ChannelFinderUnavailableError`, `ChannelFinderQueryError` |
| Kubernetes | `providers/kubernetes/kubernetes.py` | official [`kubernetes`](https://pypi.org/project/kubernetes/) client (sync client, offloaded via `asyncio.to_thread`) | `KUBECONFIG` (or in-cluster config), `K8S_NAMESPACE_DEFAULT`, `K8S_IOC_LABEL_SELECTOR_TEMPLATE` | `KubernetesUnavailableError`, `KubernetesResourceNotFoundError` |
| ArgoCD | `providers/argocd/argocd.py` | REST: `/api/v1/applications` | `ARGOCD_SERVER_URL`, `ARGOCD_AUTH_TOKEN` | `ArgoCDUnavailableError`, `ArgoCDAuthError` |
| Logbook | `providers/logbook/logbook.py` | olog-compatible REST (`/Olog/logs`) | `LOGBOOK_BASE_URL`, `LOGBOOK_USERNAME`/`PASSWORD` | `LogbookUnavailableError`, `LogbookQueryError` |
| Elasticsearch | `providers/elastic/elasticsearch.py` | official [`elasticsearch`](https://pypi.org/project/elasticsearch/) async client | `ELASTIC_URL`, `ELASTIC_API_KEY`, `ELASTIC_DEFAULT_INDEX` | `ElasticsearchUnavailableError`, `ElasticsearchQueryError` |
| Documentation | `providers/documentation/rag.py` | local TF-IDF (`scikit-learn`) over a docs folder — no external service | `DOCS_PATH`, `DOCS_INDEX_PATH` | `DocumentationUnconfiguredError`, `DocumentationIndexError` |
| Documentation (RAGFLOW) | `providers/documentation/ragflow.py` | REST: RAGFLOW's own `/api/v1/retrieval` — called server-to-server, not via RAGFLOW's separate MCP bridge | `DOCUMENTATION_BACKEND=ragflow`, `RAGFLOW_BASE_URL`, `RAGFLOW_API_KEY`, `RAGFLOW_DATASET_IDS` | `DocumentationUnconfiguredError`, `DocumentationUnavailableError`, `DocumentationTimeoutError`, `DocumentationQueryError` |

## Notes

- **EPICS is the only provider expected to have live credentials by
  default.** Every other provider is real, working code — it just reports
  `unconfigured` until you point it at a real endpoint.
- **ChannelFinder is the device metadata source of truth** — see
  [ADR 0002](adr/0002-device-metadata-source-of-truth.md).
- **Documentation defaults to local TF-IDF**, not embeddings — see
  [ADR 0003](adr/0003-local-tfidf-documentation-default.md). The
  `DocumentationProvider` protocol (`providers/documentation/interface.py`)
  is deliberately separate from `rag.py`'s implementation, which is why
  swapping in `ragflow.py` (set `DOCUMENTATION_BACKEND=ragflow`) needed no
  changes to `documentation_service.py` or the `search_documentation` tool —
  exactly the drop-in replacement ADR 0003 anticipated.
- **Kubernetes and pod status are cached** (30s TTL) via
  `OperationsService`'s injected `AsyncTTLCache`; `restart_ioc` explicitly
  invalidates the relevant cache key. **ChannelFinder-derived device metadata
  is cached** (300s TTL) inside `DeviceService`. **Live PV values are never
  cached.**
