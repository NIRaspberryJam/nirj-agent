import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


class DesktopWallpaperError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def __call__(self, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]: ...


class DesktopWallpaperManager:
    def __init__(
        self,
        runner: CommandRunner = subprocess.run,
        environment: Mapping[str, str] = os.environ,
    ) -> None:
        self.runner = runner
        self.environment = environment

    def apply(self, path: Path) -> None:
        desktop = self.environment.get("XDG_CURRENT_DESKTOP", "").lower()

        if "xfce" in desktop:
            self._apply_xfce(path)
            return
        if "gnome" in desktop:
            uri = path.resolve().as_uri()
            self._run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri]
            )
            self._run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri-dark",
                    uri,
                ]
            )
            return
        if any(name in desktop for name in ("labwc", "lxde", "lxqt", "wayfire")):
            self._run(["pcmanfm", "--set-wallpaper", str(path)])
            return

        raise DesktopWallpaperError(
            f"Unsupported desktop environment: {desktop or 'unknown'}"
        )

    def _apply_xfce(self, path: Path) -> None:
        result = self._run(["xfconf-query", "-c", "xfce4-desktop", "-l"])
        properties = [
            line
            for line in result.stdout.splitlines()
            if line.endswith("/last-image")
        ]
        if not properties:
            raise DesktopWallpaperError("XFCE has no wallpaper properties")
        for property_name in properties:
            self._run(
                [
                    "xfconf-query",
                    "-c",
                    "xfce4-desktop",
                    "-p",
                    property_name,
                    "-s",
                    str(path),
                ]
            )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(args, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise DesktopWallpaperError(
                f"Command {' '.join(args)} failed: {detail.strip()}"
            ) from exc
