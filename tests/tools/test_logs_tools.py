import json

import httpx
import respx

from argus.mcp_server.server import build_registry


async def test_search_pod_logs_unconfigured_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("search_pod_logs", {"namespace": "btf"}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "loki_unconfigured"


@respx.mock
async def test_search_pod_logs_success(app_context):
    app_context.loki._settings.base_url = "http://loki.test"
    respx.get("http://loki.test/loki/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [
                        {
                            "stream": {"namespace": "btf", "pod": "ioc-qf12-abc", "container": "ioc"},
                            "values": [["1700000000000000000", "IOC started"]],
                        }
                    ],
                },
            },
        )
    )
    registry = build_registry()
    response = await registry.dispatch(
        "search_pod_logs", {"namespace": "btf", "pod": "ioc-qf12-abc"}, app_context
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["logs"][0]["line"] == "IOC started"


async def test_get_logs_missing_query_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("get_logs", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"
