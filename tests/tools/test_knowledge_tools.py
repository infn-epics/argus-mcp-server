import base64
import json

import httpx
import respx

from argus.config.settings import GitHubSettings
from argus.core.context import AppContext
from argus.mcp_server.server import build_registry
from argus.providers.git.github import GitHubProvider
from argus.services.knowledge_service import KnowledgeService


def _disabled_github_context(app_context: AppContext) -> AppContext:
    disabled_github = GitHubProvider(GitHubSettings(_env_file=None, GITHUB_BASE_URL=""))
    return AppContext(
        **{
            **app_context.__dict__,
            "github": disabled_github,
            "knowledge_service": KnowledgeService(github=disabled_github, gitlab=app_context.gitlab),
        }
    )


async def test_search_knowledge_base_without_repos_returns_empty_list(app_context):
    registry = build_registry()
    response = await registry.dispatch("search_knowledge_base", {"query": "magnet interlock"}, app_context)
    payload = json.loads(response[0].text)
    assert payload == {"status": "success", "issues": []}


async def test_search_knowledge_base_missing_query_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("search_knowledge_base", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_get_config_history_unconfigured_repo_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history",
        {"repo": "https://github.com/infn-epics/ioc-chart.git", "path": "values.yaml"},
        _disabled_github_context(app_context),
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "github_unconfigured"


async def test_get_config_history_unknown_host_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history",
        {"repo": "https://gitea.example.org/x/y.git", "path": "values.yaml"},
        app_context,
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "unsupported_git_host"


@respx.mock
async def test_get_config_history_with_ref_returns_file_content(app_context: AppContext):
    configured_github = GitHubProvider(GitHubSettings(_env_file=None, GITHUB_TOKEN="ghp_test"))
    configured_context = AppContext(
        **{
            **app_context.__dict__,
            "github": configured_github,
            "knowledge_service": KnowledgeService(github=configured_github, gitlab=app_context.gitlab),
        }
    )
    encoded = base64.b64encode(b"beamline: BTF\ndevgroup: mag\n").decode()
    respx.get("https://api.github.com/repos/infn-epics/epik8s-btf/contents/deploy/values.yaml").mock(
        return_value=httpx.Response(200, json={"content": encoded, "encoding": "base64", "sha": "abc123"})
    )
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history",
        {
            "repo": "https://github.com/infn-epics/epik8s-btf.git",
            "path": "deploy/values.yaml",
            "ref": "HEAD",
        },
        configured_context,
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert "devgroup: mag" in payload["content"]
    assert payload["sha"] == "abc123"


async def test_get_config_history_missing_path_defaults_to_deploy_values_yaml(app_context):
    # No "path" given - should default to deploy/values.yaml and proceed all the way to
    # the explicitly disabled provider rather than bailing out on a validation error
    # for the omitted path.
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history",
        {"repo": "https://github.com/infn-epics/ioc-chart.git"},
        _disabled_github_context(app_context),
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "github_unconfigured"


async def test_get_config_history_missing_repo_without_default_returns_validation_error(app_context):
    # app_context's KnowledgeService has no default_repos configured, so omitting repo
    # here has nothing to fall back to.
    registry = build_registry()
    response = await registry.dispatch("get_config_history", {"path": "deploy/values.yaml"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


@respx.mock
async def test_get_config_history_missing_repo_uses_configured_default(app_context: AppContext):
    configured_github = GitHubProvider(GitHubSettings(_env_file=None, GITHUB_TOKEN="ghp_test"))
    configured_context = AppContext(
        **{
            **app_context.__dict__,
            "github": configured_github,
            "knowledge_service": KnowledgeService(
                github=configured_github,
                gitlab=app_context.gitlab,
                default_repos=["https://github.com/infn-epics/epik8s-btf.git"],
            ),
        }
    )
    encoded = base64.b64encode(b"beamline: BTF\ndevgroup: mag\n").decode()
    respx.get("https://api.github.com/repos/infn-epics/epik8s-btf/contents/deploy/values.yaml").mock(
        return_value=httpx.Response(200, json={"content": encoded, "encoding": "base64", "sha": "abc123"})
    )
    registry = build_registry()
    # No repo, no path - both fall back to the configured default repo and deploy/values.yaml.
    response = await registry.dispatch("get_config_history", {"ref": "HEAD"}, configured_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert "devgroup: mag" in payload["content"]
