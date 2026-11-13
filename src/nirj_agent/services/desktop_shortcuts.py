from dataclasses import dataclass

from nirj_agent.storage.files import FileStoreError, write_bytes
from nirj_agent.storage.paths import AgentPaths


VSCODE_DESKTOP_ENTRY = b"""[Desktop Entry]
Version=1.0
Type=Application
Name=Visual Studio Code
Exec=/usr/bin/code %F
Icon=/usr/share/pixmaps/vscode.png
Terminal=false
Categories=Development;IDE;
StartupNotify=true
"""

SONIC_PI_DESKTOP_ENTRY = b"""[Desktop Entry]
Version=1.0
Type=Application
Name=Sonic Pi
Exec=/usr/bin/pw-jack /usr/bin/sonic-pi
Icon=sonic-pi
Terminal=false
Categories=AudioVideo;Audio;Development;
StartupNotify=true
"""


@dataclass(frozen=True)
class DesktopShortcut:
    filename: str
    content: bytes


SHORTCUTS = {
    "sonic-pi": DesktopShortcut(
        filename="sonic-pi.desktop",
        content=SONIC_PI_DESKTOP_ENTRY,
    ),
    "vscode": DesktopShortcut(
        filename="visual-studio-code.desktop",
        content=VSCODE_DESKTOP_ENTRY,
    ),
}


SHORTCUT_PACKAGES = {
    "vscode": frozenset({"code"}),
    "sonic-pi": frozenset({"sonic-pi", "pipewire-jack"}),
}


def desktop_shortcuts_need_reconcile(
    paths: AgentPaths, desired: tuple[str, ...], vscode_profile: dict | None = None,
) -> bool:
    try:
        for shortcut_id, shortcut in SHORTCUTS.items():
            path = paths.desktop_dir / shortcut.filename
            content = _content(shortcut_id, shortcut, vscode_profile)
            if shortcut_id in desired:
                if not path.exists() or path.read_bytes() != content:
                    return True
                if path.stat().st_mode & 0o777 != 0o755:
                    return True
            elif path.exists():
                return True
        menu = paths.applications_dir / "sonic-pi.desktop"
        if "sonic-pi" in desired:
            if not menu.exists() or menu.read_bytes() != SONIC_PI_DESKTOP_ENTRY:
                return True
            return _vscode_menu_needs_reconcile(paths, vscode_profile)
        if menu.exists():
            return True
        return _vscode_menu_needs_reconcile(paths, vscode_profile)
    except OSError as exc:
        raise DesktopShortcutError(f"Could not inspect desktop shortcuts: {exc}") from exc


def _content(shortcut_id, shortcut, profile):
    if shortcut_id == "vscode" and profile is not None:
        from .vscode import desktop_entry
        return desktop_entry(profile)
    return shortcut.content


def _vscode_menu_needs_reconcile(paths, profile):
    menu = paths.applications_dir / "code.desktop"
    if profile is None:
        return menu.exists()
    from .vscode import desktop_entry
    return not menu.exists() or menu.read_bytes() != desktop_entry(profile)


class DesktopShortcutError(RuntimeError):
    pass


def reconcile_desktop_shortcuts(
    paths: AgentPaths,
    desired: tuple[str, ...],
    vscode_profile: dict | None = None,
) -> None:
    desired_set = set(desired)

    try:
        for shortcut_id, shortcut in SHORTCUTS.items():
            path = paths.desktop_dir / shortcut.filename

            if shortcut_id in desired_set:
                write_bytes(path, _content(shortcut_id, shortcut, vscode_profile))
                path.chmod(0o755)
            else:
                path.unlink(missing_ok=True)
        menu = paths.applications_dir / "sonic-pi.desktop"
        if "sonic-pi" in desired_set:
            write_bytes(menu, SONIC_PI_DESKTOP_ENTRY)
            menu.chmod(0o644)
        else:
            menu.unlink(missing_ok=True)
        code_menu = paths.applications_dir / "code.desktop"
        if vscode_profile is not None:
            from .vscode import desktop_entry
            write_bytes(code_menu, desktop_entry(vscode_profile))
            code_menu.chmod(0o644)
        else:
            code_menu.unlink(missing_ok=True)
    except (OSError, FileStoreError) as exc:
        raise DesktopShortcutError(
            f"Could not reconcile desktop shortcuts: {exc}"
        ) from exc
