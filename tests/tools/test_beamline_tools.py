import base64
import json

import httpx
import respx

from argus.config.settings import GitHubSettings
from argus.core.context import AppContext
from argus.mcp_server.server import build_registry
from argus.providers.git.github import GitHubProvider
from argus.services.beamline_inventory_service import BeamlineInventoryService
from argus.services.knowledge_service import KnowledgeService

_YAML = """
iocDefaults:
  danfysik:
    devtype: sys8x00
    devgroup: mag

epicsConfiguration:
  iocs:
    - name: "danfysik-1"
      iocprefix: "BTF:MAG:DANFYSIK"
      template: "danfysik"
      zones: TL
      devices:
        - name: QUATM002
          geo: 53
        - name: DHRTB101
          geo: 29
"""


def _configured_context(app_context: AppContext) -> AppContext:
    configured_github = GitHubProvider(GitHubSettings(_env_file=None, GITHUB_TOKEN="ghp_test"))
    knowledge_service = KnowledgeService(github=configured_github, gitlab=app_context.gitlab)
    return AppContext(
        **{
            **app_context.__dict__,
            "github": configured_github,
            "knowledge_service": knowledge_service,
            "beamline_inventory_service": BeamlineInventoryService(knowledge=knowledge_service),
        }
    )


@respx.mock
async def test_list_beamline_devices_classifies_magnets(app_context: AppContext):
    encoded = base64.b64encode(_YAML.encode()).decode()
    respx.get("https://api.github.com/repos/infn-epics/epik8s-btf/contents/deploy/values.yaml").mock(
        return_value=httpx.Response(200, json={"content": encoded, "encoding": "base64", "sha": "abc123"})
    )
    registry = build_registry()
    response = await registry.dispatch(
        "list_beamline_devices",
        {"repo": "https://github.com/infn-epics/epik8s-btf.git", "devgroup": "mag", "devfunc": "QUA"},
        _configured_context(app_context),
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "success"
    assert payload["device_count"] == 1
    assert payload["devices"][0]["name"] == "QUATM002"
    assert payload["devices"][0]["devfunc"] == "QUA"


async def test_list_beamline_devices_missing_repo_returns_validation_error(app_context):
    registry = build_registry()
    response = await registry.dispatch("list_beamline_devices", {}, app_context)
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "validation_error"


async def test_list_beamline_devices_unconfigured_repo_returns_structured_error(app_context):
    registry = build_registry()
    response = await registry.dispatch(
        "list_beamline_devices",
        {"repo": "https://github.com/infn-epics/epik8s-btf.git"},
        app_context,
    )
    payload = json.loads(response[0].text)
    assert payload["status"] == "error"
    assert payload["code"] == "github_unconfigured"
