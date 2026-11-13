import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from nirj_agent.manifests import parse_manifest
from nirj_agent.manifests.vscode import validate_profile
from nirj_agent.services.desktop_shortcuts import reconcile_desktop_shortcuts, desktop_shortcuts_need_reconcile
from nirj_agent.services.vscode import reconcile_vscode, vscode_setup_needs_reconcile, VSCodeSetupError
from nirj_agent.storage.paths import AgentPaths


PROFILE = validate_profile({
    "schema": 1, "folder": "/home/jam/jam-day",
    "extensions": ["ms-python.python", "ms-python.debugpy"],
    "settings": {"chat.disableAIFeatures": True, "window.restoreWindows": "none"},
    "runtime": {"password-store": "basic"},
})


def manifest():
    return replace(parse_manifest(b"schema: 1\napt:\n  packages: [code]\n"),
                   vscode_config_url="https://example.test/vscode.yaml", vscode_profile=PROFILE)


def test_profile_applies_as_user_preserves_settings_and_skips_installed_extensions(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    home = paths.desktop_dir.parent
    settings = home / ".config/Code/User/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('// Classroom settings\n{ "editor.fontSize": 18, "chat.disableAIFeatures": false, }\n')
    calls = []
    installed = {"ms-python.python"}

    def runner(command, **kwargs):
        calls.append(command)
        if "--install-extension" in command:
            installed.add(command[command.index("--install-extension") + 1])
        return SimpleNamespace(returncode=0, stderr="", stdout="\n".join(sorted(installed)))

    assert vscode_setup_needs_reconcile(paths, manifest())
    reconcile_vscode(paths, manifest(), runner)
    assert (home / "jam-day").is_dir()
    assert '// Classroom settings' in settings.read_text()
    assert '"editor.fontSize": 18' in settings.read_text()
    assert '"chat.disableAIFeatures": true' in settings.read_text()
    argv = json.loads((home / ".vscode/argv.json").read_text())
    assert argv["password-store"] == "basic"
    installs = [call for call in calls if "--install-extension" in call]
    assert len(installs) == 1
    assert installs[0][-3:] == ["--install-extension", "ms-python.debugpy", "--do-not-include-pack-dependencies"]
    assert all(f"HOME={home}" in call for call in calls)
    assert not vscode_setup_needs_reconcile(paths, manifest())
    (home / "jam-day/example.py").write_text("print('keep')")
    reconcile_vscode(paths, manifest(), runner)
    assert (home / "jam-day/example.py").exists()
    assert len([call for call in calls if "--install-extension" in call]) == 1


def test_extension_failure_is_reported(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    paths.desktop_dir.parent.mkdir(parents=True)
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=1, stderr="Marketplace unavailable", stdout="")
    with pytest.raises(VSCodeSetupError, match="Marketplace unavailable"):
        reconcile_vscode(paths, manifest(), runner)


def test_zero_exit_without_extension_is_not_success(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    paths.desktop_dir.parent.mkdir(parents=True)
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=0, stderr="", stdout="")
    with pytest.raises(VSCodeSetupError, match="missing after installation"):
        reconcile_vscode(paths, manifest(), runner)


def test_workspace_cannot_follow_symlink_outside_home(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    paths.desktop_dir.parent.mkdir(parents=True)
    (paths.desktop_dir.parent / "jam-day").symlink_to(tmp_path)
    with pytest.raises(VSCodeSetupError, match="outside"):
        vscode_setup_needs_reconcile(paths, manifest())


def test_launchers_open_workspace_with_logo_and_are_removed_when_disabled(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    reconcile_desktop_shortcuts(paths, ("vscode",), PROFILE)
    desktop = paths.desktop_dir / "visual-studio-code.desktop"
    menu = paths.applications_dir / "code.desktop"
    assert desktop.read_bytes() == menu.read_bytes()
    assert b'--new-window "/home/jam/jam-day"' in desktop.read_bytes()
    assert b"Icon=/usr/share/pixmaps/vscode.png" in desktop.read_bytes()
    assert not desktop_shortcuts_need_reconcile(paths, ("vscode",), PROFILE)
    reconcile_desktop_shortcuts(paths, ())
    assert not menu.exists()


def test_profile_can_disable_ai_and_account_providers_for_classroom_launch():
    from nirj_agent.services.vscode import desktop_entry
    profile = validate_profile({"schema": 1, "disabled_extensions": [
        "vscode.github-authentication", "vscode.microsoft-authentication",
    ]})
    entry = desktop_entry(profile).decode()
    assert "--disable-extension vscode.github-authentication" in entry
    assert "--disable-extension vscode.microsoft-authentication" in entry


def test_profile_failure_is_recorded_without_promoting_manifest(tmp_path, monkeypatch):
    import nirj_agent.services.apply as apply
    from nirj_agent.config import DeviceType, create_config
    from nirj_agent.state import load_state
    import yaml

    paths = AgentPaths.sandbox(tmp_path)
    paths.desktop_dir.parent.mkdir(parents=True)
    create_config("TEST-001", DeviceType.PI5, paths.config)
    paths.manifest_cache.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_cache.write_bytes(yaml.safe_dump({
        "schema": 1, "apt": {"packages": ["code"]},
        "vscode": {"config_url": "https://example.test/profile", "_profile": PROFILE},
    }).encode())
    class Packages:
        def list_installed(self):
            return {"code"}
    class Python:
        def list_installed(self):
            return {}
    def fail(*args):
        raise VSCodeSetupError("Marketplace unavailable")
    monkeypatch.setattr(apply, "reconcile_vscode", fail)
    with pytest.raises(apply.PartialApplyError, match="Marketplace unavailable"):
        apply.apply_manifest(paths, Packages(), Python())
    state = load_state(paths.state)
    assert not state.ready
    assert state.manifest_hash is None
    assert "Marketplace unavailable" in state.errors
    assert not paths.current_manifest.exists()
