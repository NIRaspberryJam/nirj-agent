import hashlib
from pathlib import Path
from uuid import UUID

import pytest

from nirj_agent.config import (
    AgentConfig,
    DeviceConfig,
    DeviceType,
    ManifestSource,
)
from nirj_agent.manifests import ManifestError
from nirj_agent.services.manifest import refresh_manifest
from nirj_agent.storage.paths import AgentPaths


class FakeClient:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.received_source = None

    def fetch(self, source):
        self.received_source = source
        return "https://example.test/manifest.yaml", self.content


def config() -> AgentConfig:
    return AgentConfig(
        device=DeviceConfig(
            id=UUID("fc41017d-0937-49f2-a49d-a64164d9cc2e"),
            asset_id="PI5-001",
            type=DeviceType.PI5,
        ),
        manifest=ManifestSource(
            type="github",
            repo="NIRaspberryJam/nirj-infra",
            path="manifests/pi5.manifest.yaml",
        ),
        overlay_enabled=False,
        background_enabled=False,
    )


def test_refresh_manifest_validates_hashes_and_caches(tmp_path: Path) -> None:
    content = b"schema: 1\napt:\n  packages: [git]\n"
    client = FakeClient(content)
    paths = AgentPaths.sandbox(tmp_path)

    document = refresh_manifest(config(), paths, client)

    assert document.content == content
    assert document.sha256 == hashlib.sha256(content).hexdigest()
    assert document.source_url == "https://example.test/manifest.yaml"
    assert document.manifest.apt.packages == ("git",)
    assert paths.manifest_cache.read_bytes() == content
    assert client.received_source == config().manifest


def test_refresh_manifest_preserves_cache_when_download_is_invalid(
    tmp_path: Path,
) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    paths.manifest_cache.parent.mkdir(parents=True)
    paths.manifest_cache.write_bytes(b"schema: 1\n")

    with pytest.raises(ManifestError):
        refresh_manifest(config(), paths, FakeClient(b"schema: ["))

    assert paths.manifest_cache.read_bytes() == b"schema: 1\n"
