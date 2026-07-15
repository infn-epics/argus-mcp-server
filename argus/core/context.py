"""Composition root: builds every provider and service from Settings.

Plain constructor injection, no DI framework. ``AppContext.build()`` is called
once at process startup by mcp_server/server.py; tests construct ``AppContext``
directly with fake providers, bypassing ``build()`` entirely.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.config.settings import Settings
from argus.core.cache import AsyncTTLCache
from argus.providers.archiver.archiver_appliance import ArchiverApplianceProvider
from argus.providers.argocd.argocd import ArgoCDProvider
from argus.providers.channelfinder.channelfinder import ChannelFinderProvider
from argus.providers.documentation.interface import DocumentationProvider
from argus.providers.documentation.rag import LocalTfidfDocumentationProvider
from argus.providers.documentation.ragflow import RagflowDocumentationProvider
from argus.providers.elastic.elasticsearch import ElasticsearchProvider
from argus.providers.epics.channel_access import ChannelAccessProvider
from argus.providers.epics.interface import EpicsProvider
from argus.providers.epics.pvaccess import PvAccessProvider
from argus.providers.kubernetes.kubernetes import KubernetesProvider
from argus.providers.git.github import GitHubProvider
from argus.providers.git.gitlab import GitLabProvider
from argus.providers.logbook.logbook import LogbookProvider
from argus.services.device_service import DeviceService
from argus.services.diagnostics_service import DiagnosticsService
from argus.services.documentation_service import DocumentationService
from argus.services.history_service import HistoryService
from argus.services.knowledge_service import KnowledgeService
from argus.services.operations_service import OperationsService, ProcedureRegistry


@dataclass
class AppContext:
    settings: Settings

    epics_ca: EpicsProvider
    epics_pva: EpicsProvider
    archiver: ArchiverApplianceProvider
    channelfinder: ChannelFinderProvider
    kubernetes: KubernetesProvider
    argocd: ArgoCDProvider
    logbook: LogbookProvider
    elastic: ElasticsearchProvider
    documentation: DocumentationProvider
    github: GitHubProvider
    gitlab: GitLabProvider

    device_cache: AsyncTTLCache
    channelfinder_cache: AsyncTTLCache
    kubernetes_cache: AsyncTTLCache
    knowledge_cache: AsyncTTLCache

    device_service: DeviceService
    diagnostics_service: DiagnosticsService
    operations_service: OperationsService
    history_service: HistoryService
    documentation_service: DocumentationService
    knowledge_service: KnowledgeService

    @classmethod
    def build(cls, settings: Settings | None = None) -> AppContext:
        settings = settings or Settings()

        epics_ca = ChannelAccessProvider(settings.epics)
        epics_pva = PvAccessProvider(settings.epics)
        archiver = ArchiverApplianceProvider(settings.archiver)
        channelfinder = ChannelFinderProvider(settings.channelfinder)
        kubernetes = KubernetesProvider(settings.kubernetes)
        argocd = ArgoCDProvider(settings.argocd)
        logbook = LogbookProvider(settings.logbook)
        elastic = ElasticsearchProvider(settings.elastic)
        documentation: DocumentationProvider
        if settings.documentation_backend == "ragflow":
            documentation = RagflowDocumentationProvider(settings.ragflow)
        else:
            documentation = LocalTfidfDocumentationProvider(settings.documentation)
        github = GitHubProvider(settings.github)
        gitlab = GitLabProvider(settings.gitlab)

        device_cache = AsyncTTLCache(ttl=settings.cache.device_ttl_seconds)
        channelfinder_cache = AsyncTTLCache(ttl=settings.cache.channelfinder_ttl_seconds)
        kubernetes_cache = AsyncTTLCache(ttl=settings.cache.kubernetes_ttl_seconds)
        knowledge_cache = AsyncTTLCache(ttl=settings.cache.knowledge_ttl_seconds)

        device_service = DeviceService(channelfinder=channelfinder, cache=device_cache)
        diagnostics_service = DiagnosticsService(
            device_service=device_service,
            epics=epics_ca,
            archiver=archiver,
            kubernetes=kubernetes,
            argocd=argocd,
            logbook=logbook,
            documentation=documentation,
        )
        operations_service = OperationsService(
            epics_ca=epics_ca,
            epics_pva=epics_pva,
            channelfinder=channelfinder,
            kubernetes=kubernetes,
            logbook=logbook,
            procedures=ProcedureRegistry(),
            kubernetes_cache=kubernetes_cache,
        )
        history_service = HistoryService(archiver=archiver, logbook=logbook, elastic=elastic)
        documentation_service = DocumentationService(documentation=documentation)
        default_repos = [r.strip() for r in settings.git_default_repos.split(",") if r.strip()]
        knowledge_service = KnowledgeService(
            github=github, gitlab=gitlab, default_repos=default_repos, cache=knowledge_cache
        )

        return cls(
            settings=settings,
            epics_ca=epics_ca,
            epics_pva=epics_pva,
            archiver=archiver,
            channelfinder=channelfinder,
            kubernetes=kubernetes,
            argocd=argocd,
            logbook=logbook,
            elastic=elastic,
            documentation=documentation,
            github=github,
            gitlab=gitlab,
            device_cache=device_cache,
            channelfinder_cache=channelfinder_cache,
            kubernetes_cache=kubernetes_cache,
            knowledge_cache=knowledge_cache,
            device_service=device_service,
            diagnostics_service=diagnostics_service,
            operations_service=operations_service,
            history_service=history_service,
            documentation_service=documentation_service,
            knowledge_service=knowledge_service,
        )
