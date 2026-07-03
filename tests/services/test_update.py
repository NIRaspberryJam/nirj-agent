import hashlib

from nirj_agent.config import DeviceType, create_config
from nirj_agent.services.update import check_for_update
from nirj_agent.storage.paths import AgentPaths


MANIFEST = b"schema: 1\napt:\n  packages: [git]\n"


class Client:
    def fetch(self, _source):
        return "https://example.test/manifest.yaml", MANIFEST


def test_check_compares_without_persisting_target(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)
    paths.current_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.current_manifest.write_bytes(MANIFEST)

    result = check_for_update(paths, Client())

    assert result.update_available is False
    assert result.current_hash == hashlib.sha256(MANIFEST).hexdigest()
    assert not paths.target_manifest.exists()


def test_check_can_persist_validated_target(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)

    result = check_for_update(paths, Client(), persist_target=True)

    assert result.update_available is True
    assert paths.target_manifest.read_bytes() == MANIFEST
