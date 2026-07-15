"""ARGUS configuration.

Every provider's settings are entirely optional so the server boots with only
EPICS configured (today's ``.env``). Absence of a provider's settings is what
makes ``Provider.is_configured()`` return False for that provider.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class _ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class EpicsSettings(_ProviderSettings):
    ca_addr_list: str | None = Field(default=None, alias="EPICS_CA_ADDR_LIST")
    ca_auto_addr_list: bool = Field(default=True, alias="EPICS_CA_AUTO_ADDR_LIST")
    pva_addr_list: str | None = Field(default=None, alias="EPICS_PVA_ADDR_LIST")


class ArchiverSettings(_ProviderSettings):
    base_url: str | None = Field(default=None, alias="ARCHIVER_BASE_URL")


class ChannelFinderSettings(_ProviderSettings):
    base_url: str | None = Field(default=None, alias="CHANNELFINDER_BASE_URL")
    username: str | None = Field(default=None, alias="CHANNELFINDER_USERNAME")
    password: str | None = Field(default=None, alias="CHANNELFINDER_PASSWORD")


class KubernetesSettings(_ProviderSettings):
    kubeconfig_path: str | None = Field(default=None, alias="KUBECONFIG")
    default_namespace: str = Field(default="default", alias="K8S_NAMESPACE_DEFAULT")
    ioc_label_selector_template: str = Field(
        default="app=ioc,device={ioc_name}", alias="K8S_IOC_LABEL_SELECTOR_TEMPLATE"
    )


class ArgoCDSettings(_ProviderSettings):
    server_url: str | None = Field(default=None, alias="ARGOCD_SERVER_URL")
    auth_token: str | None = Field(default=None, alias="ARGOCD_AUTH_TOKEN")


class LogbookSettings(_ProviderSettings):
    base_url: str | None = Field(default=None, alias="LOGBOOK_BASE_URL")
    username: str | None = Field(default=None, alias="LOGBOOK_USERNAME")
    password: str | None = Field(default=None, alias="LOGBOOK_PASSWORD")


class ElasticSettings(_ProviderSettings):
    url: str | None = Field(default=None, alias="ELASTIC_URL")
    api_key: str | None = Field(default=None, alias="ELASTIC_API_KEY")
    default_index: str = Field(default="argus-logs", alias="ELASTIC_DEFAULT_INDEX")


class DocumentationSettings(_ProviderSettings):
    docs_path: str | None = Field(default=None, alias="DOCS_PATH")
    index_path: str | None = Field(default=None, alias="DOCS_INDEX_PATH")


class RagflowSettings(_ProviderSettings):
    base_url: str | None = Field(default=None, alias="RAGFLOW_BASE_URL")
    api_key: str | None = Field(default=None, alias="RAGFLOW_API_KEY")
    # Comma-separated dataset IDs to search. Left unset, the query searches
    # every dataset the API key can access -- slower (embedding+rerank over
    # a wider corpus), so timeout_seconds defaults higher than a scoped
    # search would need.
    dataset_ids: str | None = Field(default=None, alias="RAGFLOW_DATASET_IDS")
    timeout_seconds: float = Field(default=20.0, alias="RAGFLOW_TIMEOUT_SECONDS")


class GitHubSettings(_ProviderSettings):
    base_url: str = Field(default="https://api.github.com", alias="GITHUB_BASE_URL")
    token: str | None = Field(default=None, alias="GITHUB_TOKEN")


class GitLabSettings(_ProviderSettings):
    base_url: str | None = Field(default=None, alias="GITLAB_BASE_URL")
    token: str | None = Field(default=None, alias="GITLAB_TOKEN")


class CacheSettings(_ProviderSettings):
    device_ttl_seconds: float = Field(default=300.0, alias="CACHE_DEVICE_TTL_SECONDS")
    channelfinder_ttl_seconds: float = Field(default=120.0, alias="CACHE_CHANNELFINDER_TTL_SECONDS")
    kubernetes_ttl_seconds: float = Field(default=30.0, alias="CACHE_KUBERNETES_TTL_SECONDS")
    # get_config_history is now the recommended first call for most beamline
    # questions (see knowledge_tools.py), so it needs a much longer TTL than
    # live-data caches above -- config files change on the order of days, not
    # seconds, and every GitHub/GitLab call is a real network round-trip.
    knowledge_ttl_seconds: float = Field(default=600.0, alias="CACHE_KNOWLEDGE_TTL_SECONDS")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    transport: Literal["stdio", "sse"] = Field(default="stdio", alias="ARGUS_TRANSPORT")
    sse_host: str = Field(default="127.0.0.1", alias="ARGUS_SSE_HOST")
    sse_port: int = Field(default=8000, alias="ARGUS_SSE_PORT")
    log_level: str = Field(default="INFO", alias="ARGUS_LOG_LEVEL")
    log_json: bool = Field(default=True, alias="ARGUS_LOG_JSON")

    # Comma-separated repo URLs search_knowledge_base searches when the
    # caller doesn't specify a repo list explicitly.
    git_default_repos: str = Field(default="", alias="GIT_DEFAULT_REPOS")

    # Which DocumentationProvider backs search_documentation. "ragflow"
    # requires ragflow.base_url + ragflow.api_key; falls back to local
    # TF-IDF behavior either way if ragflow isn't actually configured.
    documentation_backend: Literal["local", "ragflow"] = Field(default="local", alias="DOCUMENTATION_BACKEND")

    epics: EpicsSettings = Field(default_factory=EpicsSettings)
    archiver: ArchiverSettings = Field(default_factory=ArchiverSettings)
    channelfinder: ChannelFinderSettings = Field(default_factory=ChannelFinderSettings)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)
    argocd: ArgoCDSettings = Field(default_factory=ArgoCDSettings)
    logbook: LogbookSettings = Field(default_factory=LogbookSettings)
    elastic: ElasticSettings = Field(default_factory=ElasticSettings)
    documentation: DocumentationSettings = Field(default_factory=DocumentationSettings)
    ragflow: RagflowSettings = Field(default_factory=RagflowSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
