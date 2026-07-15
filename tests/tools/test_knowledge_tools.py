import json

from argus.mcp_server.server import build_registry


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


async def test_get_config_history_missing_path_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "get_config_history", {"repo": "https://github.com/infn-epics/ioc-chart.git"}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"
