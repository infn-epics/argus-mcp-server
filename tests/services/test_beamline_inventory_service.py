from argus.providers.git.models import FileContent
from argus.services.beamline_inventory_service import BeamlineInventoryService

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

    - name: "mag-wrapper"
      iocprefix: "DAFNE"
      devgroup: mag
      devices:
        - name: DANTE01
          zones: BTF2

    - name: "unimotor"
      iocprefix: "BTF:MOT"
      devgroup: mot
      devices:
        - name: SLTTB004R
          zones:
            - BTF1
            - BTF2

    - name: "no-devices-ioc"
      iocprefix: "BTF:EMPTY"
      devgroup: diag
"""


class _FakeKnowledge:
    def __init__(self, content: str = _YAML) -> None:
        self._content = content
        self.calls = 0

    async def get_file(self, repo, path, ref="HEAD"):
        self.calls += 1
        return FileContent(repo=repo, path=path, ref=ref, content=self._content, sha="abc")


async def test_devgroup_inherited_from_ioc_defaults_via_template():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git")
    danfysik_devices = [d for d in devices if d.ioc_name == "danfysik-1"]
    assert len(danfysik_devices) == 2
    assert all(d.devgroup == "mag" for d in danfysik_devices)
    assert all(d.devtype == "sys8x00" for d in danfysik_devices)


async def test_devfunc_classified_by_name_within_mag_group():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = {d.name: d for d in await service.list_devices("https://example.git")}
    assert devices["QUATM002"].devfunc == "QUA"
    assert devices["DHRTB101"].devfunc == "DIP"


async def test_explicit_ioc_level_devgroup_without_template():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git")
    dante = next(d for d in devices if d.name == "DANTE01")
    assert dante.devgroup == "mag"
    assert dante.zones == ["BTF2"]


async def test_mot_group_falls_back_to_generic_devfunc():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git")
    slt = next(d for d in devices if d.name == "SLTTB004R")
    assert slt.devfunc == "SLT"
    assert slt.zones == ["BTF1", "BTF2"]


async def test_filter_by_devgroup():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git", devgroup="mag")
    assert {d.name for d in devices} == {"QUATM002", "DHRTB101", "DANTE01"}


async def test_filter_by_devfunc():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git", devgroup="mag", devfunc="QUA")
    assert {d.name for d in devices} == {"QUATM002"}


async def test_filter_by_zone():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git", zone="BTF2")
    assert {d.name for d in devices} == {"DANTE01", "SLTTB004R"}


async def test_ioc_without_devices_contributes_nothing():
    service = BeamlineInventoryService(knowledge=_FakeKnowledge())
    devices = await service.list_devices("https://example.git")
    assert all(d.ioc_name != "no-devices-ioc" for d in devices)


async def test_uses_knowledge_service_cache_transparently():
    fake = _FakeKnowledge()
    service = BeamlineInventoryService(knowledge=fake)
    await service.list_devices("https://example.git")
    assert fake.calls == 1
