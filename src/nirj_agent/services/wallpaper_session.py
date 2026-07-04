import logging
from pathlib import Path
from threading import Event

from nirj_agent.config import load_config
from nirj_agent.storage.paths import AgentPaths

from .desktop import DesktopWallpaperError, DesktopWallpaperManager


logger = logging.getLogger(__name__)


def watch_wallpaper(
    paths: AgentPaths,
    stop_event: Event,
    desktop: DesktopWallpaperManager,
    poll_interval: float = 1.0,
) -> None:
    wallpaper = paths.generated_dir / "wallpaper.png"
    last_applied: tuple[int, int] | None = None

    while not stop_event.is_set():
        config = load_config(paths.config)
        if config.background_enabled:
            signature = _signature(wallpaper)
            if signature is not None and signature != last_applied:
                try:
                    desktop.apply(wallpaper)
                except DesktopWallpaperError as exc:
                    logger.warning("Could not apply wallpaper: %s", exc)
                else:
                    last_applied = signature
        else:
            last_applied = None

        stop_event.wait(poll_interval)


def _signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size
