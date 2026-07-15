import base64
import json

import httpx
import respx

from argus.config.settings import GitHubSettings
from argus.core.context import AppContext
from argus.mcp_server.server import build_registry
from argus.providers.git.github import GitHubProvider
from argus.services.knowledge_service import KnowledgeService


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
        app_context,
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


async def test_get_config_history_missing_path_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history", {"repo": "https://github.com/infn-epics/ioc-chart.git"}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"
