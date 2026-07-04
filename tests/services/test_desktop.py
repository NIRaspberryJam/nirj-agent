import subprocess
from pathlib import Path

import pytest

from nirj_agent.services.desktop import (
    DesktopWallpaperError,
    DesktopWallpaperManager,
)


def result(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout, "")


def test_pcmanfm_desktops_apply_wallpaper() -> None:
    calls = []

    def run(args, **_kwargs):
        calls.append(args)
        return result()

    manager = DesktopWallpaperManager(
        runner=run,
        environment={"XDG_CURRENT_DESKTOP": "LXDE-pi:labwc"},
    )
    manager.apply(Path("/tmp/wallpaper.png"))

    assert calls == [["pcmanfm", "--set-wallpaper", "/tmp/wallpaper.png"]]


def test_xfce_updates_every_monitor_property() -> None:
    calls = []

    def run(args, **_kwargs):
        calls.append(args)
        if args[-1] == "-l":
            return result(
                "/backdrop/screen0/monitor0/workspace0/last-image\n"
                "/backdrop/screen0/monitor1/workspace0/last-image\n"
            )
        return result()

    manager = DesktopWallpaperManager(
        runner=run,
        environment={"XDG_CURRENT_DESKTOP": "XFCE"},
    )
    manager.apply(Path("/tmp/wallpaper.png"))

    assert len(calls) == 3
    assert calls[1][-2:] == ["-s", "/tmp/wallpaper.png"]
    assert calls[2][-2:] == ["-s", "/tmp/wallpaper.png"]


def test_unknown_desktop_is_rejected() -> None:
    manager = DesktopWallpaperManager(environment={})

    with pytest.raises(DesktopWallpaperError, match="unknown"):
        manager.apply(Path("/tmp/wallpaper.png"))
