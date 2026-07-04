from pathlib import Path

from nirj_agent.storage.files import FileStoreError, write_bytes
from nirj_agent.storage.paths import AgentPaths


AUTOSTART_CONTENT = b"""[Desktop Entry]
Type=Application
Name=NIRJ Wallpaper Agent
Exec=/usr/local/bin/nirj-agent wallpaper watch
NoDisplay=true
X-GNOME-Autostart-enabled=true
"""


class DesktopSetupError(RuntimeError):
    pass


def desktop_setup_needs_reconcile(
    paths: AgentPaths,
    enabled: bool,
) -> bool:
    if not enabled:
        return paths.wallpaper_autostart.exists()

    source = _read_required(paths.source_background)
    return (
        _read_optional(paths.base_background) != source
        or _read_optional(paths.wallpaper_autostart) != AUTOSTART_CONTENT
    )


def reconcile_desktop_setup(paths: AgentPaths, enabled: bool) -> None:
    try:
        if enabled:
            source = _read_required(paths.source_background)
            write_bytes(paths.base_background, source)
            write_bytes(paths.wallpaper_autostart, AUTOSTART_CONTENT)
        else:
            paths.wallpaper_autostart.unlink(missing_ok=True)
    except (OSError, FileStoreError) as exc:
        raise DesktopSetupError(
            f"Could not reconcile wallpaper desktop setup: {exc}"
        ) from exc


def _read_required(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DesktopSetupError(
            f"Could not read wallpaper asset {path}: {exc}"
        ) from exc


def _read_optional(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DesktopSetupError(f"Could not read {path}: {exc}") from exc
