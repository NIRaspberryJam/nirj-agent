import json
import os
import subprocess

import pytest

from nirj_agent.services.python_setup import (
    START,
    _settings,
    python_setup_needs_reconcile,
    reconcile_python_setup,
)
from nirj_agent.services.desktop_setup import (
    desktop_setup_needs_reconcile,
    reconcile_desktop_setup,
)
from nirj_agent.storage.paths import AgentPaths


def prepare(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    home = paths.desktop_dir.parent
    home.mkdir(parents=True)
    binary = paths.python_environment / "bin/python"
    binary.parent.mkdir(parents=True)
    binary.symlink_to("/usr/bin/python3")
    return paths, home


def test_setup_preserves_content_permissions_and_is_idempotent(tmp_path):
    paths, home = prepare(tmp_path)
    profile = home / ".profile"
    profile.write_text("export MY_SETTING=hello\n")
    profile.chmod(0o600)
    (home / ".bash_profile").write_text("# custom login\n")
    assert desktop_setup_needs_reconcile(paths, False)
    reconcile_desktop_setup(paths, False)
    assert not desktop_setup_needs_reconcile(paths, False)
    assert profile.read_text().startswith("export MY_SETTING=hello\n")
    assert profile.stat().st_mode & 0o777 == 0o600
    assert profile.stat().st_uid == home.stat().st_uid
    for name in (".profile", ".bashrc", ".xprofile", ".bash_profile"):
        assert (home / name).read_text().count(START) == 1
    settings = home / ".config/Code/User/settings.json"
    assert json.loads(settings.read_text())["python.defaultInterpreterPath"] == str(paths.python_environment / "bin/python")
    before = profile.stat().st_mtime_ns
    reconcile_python_setup(paths)
    assert profile.stat().st_mtime_ns == before


def test_shell_resolves_managed_python_and_respects_active_venv(tmp_path):
    paths, home = prepare(tmp_path)
    reconcile_python_setup(paths)
    command = '. "$HOME/.profile"; . "$HOME/.profile"; command -v python; printf "%s" "$PATH"'
    env = {**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin", "VIRTUAL_ENV": ""}
    result = subprocess.run(["/bin/sh", "-c", command], env=env, capture_output=True, text=True, check=True)
    binary, path = result.stdout.split("\n", 1)
    assert binary == str(paths.python_environment / "bin/python")
    assert path.split(":").count(str(paths.python_environment / "bin")) == 1
    env["VIRTUAL_ENV"] = "/another/venv"
    result = subprocess.run(["/bin/sh", "-c", '. "$HOME/.profile"; printf "%s" "$PATH"'], env=env, capture_output=True, text=True, check=True)
    assert result.stdout == "/usr/bin:/bin"


def test_jsonc_preserves_comments_nested_settings_and_trailing_commas():
    content = '''{
// keep this
"editor.fontSize": 16,
"nested": {"python.defaultInterpreterPath": "untouched",},
"python.defaultInterpreterPath": "/old/python", /* keep too */
}'''
    result = _settings(content, "/new/python")
    assert result == content.replace('"/old/python"', '"/new/python"')
    assert _settings(result, "/new/python") == result
    added = _settings('{/* comment */ "url": "https://example.test",}', "/new/python")
    assert '"url": "https://example.test"' in added
    assert _settings(added, "/new/python") == added


def test_missing_environment_or_user_does_not_create_configuration(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    reconcile_python_setup(paths)
    assert not paths.desktop_dir.parent.exists()
    paths.desktop_dir.parent.mkdir(parents=True)
    assert not python_setup_needs_reconcile(paths)


def test_invalid_settings_are_not_overwritten(tmp_path):
    paths, home = prepare(tmp_path)
    settings = home / ".config/Code/User/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{ broken")
    with pytest.raises(ValueError):
        reconcile_python_setup(paths)
    assert settings.read_text() == "{ broken"
    assert not (home / ".profile").exists()
