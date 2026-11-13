"""Apply a downloaded VS Code profile to the classroom user's session."""

import os
from pathlib import Path
import subprocess

from nirj_agent.manifests.models import Manifest
from nirj_agent.storage.paths import AgentPaths
from nirj_agent.storage.files import FileStoreError
from .python_setup import merge_setting
from .user_files import user_directory, write_user_file


class VSCodeSetupError(RuntimeError):
    pass


def workspace_path(paths: AgentPaths, profile: dict) -> Path:
    home = paths.desktop_dir.parent
    folder = home / Path(profile["folder"]).relative_to("/home/jam")
    if folder.resolve() == home.resolve() or not folder.resolve().is_relative_to(home.resolve()):
        raise VSCodeSetupError("VS Code workspace resolves outside the jam home directory")
    return folder


def desktop_entry(profile: dict) -> bytes:
    # Desktop Entry argument quoting differs from shell quoting. Profile paths are
    # validated, but still escape quotes, backslashes, dollars and literal %.
    folder = profile["folder"].replace("%", "%%")
    for character in ('\\', '"', '`', '$'):
        folder = folder.replace(character, '\\' + character)
    disabled = "".join(" --disable-extension " + item for item in profile.get("disabled_extensions", []))
    return ("[Desktop Entry]\nVersion=1.0\nType=Application\n"
            "Name=Visual Studio Code\n"
            f'Exec=/usr/bin/code --new-window{disabled} "{folder}"\n'
            "Icon=/usr/share/pixmaps/vscode.png\nTerminal=false\n"
            "Categories=Development;IDE;\nStartupNotify=true\n").encode()


def _file_changes(paths: AgentPaths, profile: dict) -> list[tuple[Path, bytes]]:
    home = paths.desktop_dir.parent
    updates = [
        (home / ".config/Code/User/settings.json", profile["settings"]),
        (home / ".vscode/argv.json", profile["runtime"]),
    ]
    changes = []
    for path, values in updates:
        content = path.read_text() if path.exists() else "{}\n"
        desired = content
        for key, value in values.items():
            desired = merge_setting(desired, key, value)
        if desired != content:
            changes.append((path, desired.encode()))
    return changes


def vscode_setup_needs_reconcile(paths: AgentPaths, manifest: Manifest) -> bool:
    if manifest.vscode_config_url and manifest.vscode_profile is None:
        raise VSCodeSetupError("VS Code profile has not been resolved")
    profile = manifest.vscode_profile
    if profile is None:
        return False
    folder = workspace_path(paths, profile)
    return not folder.is_dir() or bool(_file_changes(paths, profile))


def reconcile_vscode(paths: AgentPaths, manifest: Manifest, runner=subprocess.run) -> None:
    if manifest.vscode_config_url and manifest.vscode_profile is None:
        raise VSCodeSetupError("VS Code profile has not been resolved")
    profile = manifest.vscode_profile
    if profile is None:
        return
    home = paths.desktop_dir.parent
    if not home.is_dir():
        raise VSCodeSetupError("The jam user home directory does not exist")
    try:
        user_directory(workspace_path(paths, profile), home)
        for path, content in _file_changes(paths, profile):
            write_user_file(path, content, home)
        import pwd
        owner = home.stat()
        username = pwd.getpwuid(owner.st_uid).pw_name
        prefix = (["runuser", "-u", username, "--"] if os.geteuid() == 0 else [])
        # Keep privileged/session environment variables out of the user's CLI.
        prefix += ["env", "-i", f"HOME={home}", f"USER={username}",
                   f"LOGNAME={username}", "PATH=/usr/local/bin:/usr/bin:/bin",
                   "/usr/bin/code", "--user-data-dir", str(home / ".config/Code"),
                   "--extensions-dir", str(home / ".vscode/extensions"),
                   "--password-store=" + profile["runtime"].get("password-store", "basic")]

        def run(arguments):
            result = runner(prefix + arguments, check=False, capture_output=True,
                            text=True, timeout=600, cwd=home)
            if result.returncode:
                raise VSCodeSetupError(
                    f"VS Code command failed: {result.stderr.strip() or result.stdout.strip()}"
                )
            return result.stdout

        if profile["extensions"]:
            installed = {line.strip().lower() for line in run(["--list-extensions"]).splitlines()}
            for extension in profile["extensions"]:
                if extension not in installed:
                    run(["--install-extension", extension, "--do-not-include-pack-dependencies"])
            installed = {line.strip().lower() for line in run(["--list-extensions"]).splitlines()}
            missing = set(profile["extensions"]) - installed
            if missing:
                raise VSCodeSetupError("VS Code extensions missing after installation: " + ", ".join(sorted(missing)))
    except (OSError, ValueError, KeyError, FileStoreError, subprocess.TimeoutExpired) as exc:
        raise VSCodeSetupError(f"Could not configure VS Code: {exc}") from exc
