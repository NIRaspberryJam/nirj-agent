import io
import json

import pytest

from nirj_agent.config import DeviceType, create_config
from nirj_agent.manifests import ManifestError, parse_manifest
from nirj_agent.manifests.vscode import resolve_profile, validate_profile
from nirj_agent.services.update import check_for_update
from nirj_agent.storage.paths import AgentPaths

MANIFEST = b"schema: 1\napt:\n  packages: [code]\nvscode:\n  config_url: https://example.test/vscode.yaml\n"


@pytest.mark.parametrize("changes", [
    {"schema": True}, {"folder": "/data/jam-day"}, {"folder": "/home/jam/../other"},
    {"extensions": ["--bad"]}, {"extensions": "ms-python.python"},
    {"settings": []}, {"runtime": {"no-sandbox": True}}, {"runtime": {"password-store": "wrong"}},
    {"settings": {"python.defaultInterpreterPath": "/usr/bin/python3"}},
])
def test_reject_invalid_profiles(changes):
    with pytest.raises((ValueError, TypeError)):
        validate_profile({"schema": 1, **changes})


@pytest.mark.parametrize("url", ["http://example.test/x", "file:///tmp/x", "https://user:pass@example.test/x"])
def test_manifest_requires_https_without_credentials(url):
    with pytest.raises(ManifestError, match="HTTPS"):
        parse_manifest(MANIFEST.replace(b"https://example.test/vscode.yaml", url.encode()))


def test_profile_download_is_embedded_and_cached_hash_detects_profile_only_changes(tmp_path, monkeypatch):
    from nirj_agent.manifests import vscode
    profile = {"schema": 1, "settings": {"chat.disableAIFeatures": True}}
    monkeypatch.setattr(vscode, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps(profile).encode()))
    paths = AgentPaths.sandbox(tmp_path)
    create_config("TEST-001", DeviceType.PI5, paths.config)
    class Client:
        def fetch(self, source):
            return "https://example.test/manifest.yaml", MANIFEST
    first = check_for_update(paths, Client(), persist_target=True)
    cached = paths.target_manifest.read_bytes()
    assert parse_manifest(cached).vscode_profile["settings"]["chat.disableAIFeatures"] is True
    paths.current_manifest.write_bytes(cached)
    assert not check_for_update(paths, Client()).update_available
    profile["settings"]["editor.fontSize"] = 18
    assert check_for_update(paths, Client()).update_available
    assert paths.target_manifest.read_bytes() == cached  # read-only check
    check_for_update(paths, Client(), persist_target=True)
    assert paths.target_manifest.read_bytes() != cached
    assert first.target_hash


def test_bad_download_does_not_replace_working_target(tmp_path, monkeypatch):
    from nirj_agent.manifests import vscode
    monkeypatch.setattr(vscode, "urlopen", lambda *args, **kwargs: io.BytesIO(b"schema: ["))
    paths = AgentPaths.sandbox(tmp_path)
    create_config("TEST-001", DeviceType.PI5, paths.config)
    paths.target_manifest.parent.mkdir(parents=True)
    paths.target_manifest.write_bytes(b"schema: 1\n")
    class Client:
        def fetch(self, source):
            return "https://example.test/manifest.yaml", MANIFEST
    with pytest.raises(ManifestError, match="resolve VS Code"):
        check_for_update(paths, Client(), persist_target=True)
    assert paths.target_manifest.read_bytes() == b"schema: 1\n"


def test_cannot_require_and_disable_the_same_extension():
    with pytest.raises(ValueError, match="both required and disabled"):
        validate_profile({"schema": 1, "extensions": ["ms-python.python"],
                          "disabled_extensions": ["MS-PYTHON.PYTHON"]})
