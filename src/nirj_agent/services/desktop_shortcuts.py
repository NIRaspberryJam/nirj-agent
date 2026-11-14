from dataclasses import dataclass

from nirj_agent.storage.files import FileStoreError, write_bytes
from nirj_agent.storage.paths import AgentPaths


VSCODE_DESKTOP_ENTRY = b"""[Desktop Entry]
Version=1.0
Type=Application
Name=Visual Studio Code
Exec=/usr/bin/code %F
Icon=visual-studio-code
Terminal=false
Categories=Development;IDE;
StartupNotify=true
"""

SONIC_PI_DESKTOP_ENTRY = b"""[Desktop Entry]
Version=1.0
Type=Application
Name=Sonic Pi
Exec=/usr/bin/sonic-pi
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


class DesktopShortcutError(RuntimeError):
    pass


def reconcile_desktop_shortcuts(
    paths: AgentPaths,
    desired: tuple[str, ...],
) -> None:
    desired_set = set(desired)

    try:
        for shortcut_id, shortcut in SHORTCUTS.items():
            path = paths.desktop_dir / shortcut.filename

            if shortcut_id in desired_set:
                write_bytes(path, shortcut.content)
                path.chmod(0o755)
            else:
                path.unlink(missing_ok=True)
    except (OSError, FileStoreError) as exc:
        raise DesktopShortcutError(
            f"Could not reconcile desktop shortcuts: {exc}"
        ) from exc
