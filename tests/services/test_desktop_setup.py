import pytest

from nirj_agent.services.desktop_setup import (
    AUTOSTART_CONTENT,
    DesktopSetupError,
    desktop_setup_needs_reconcile,
    reconcile_desktop_setup,
)
from nirj_agent.storage.paths import AgentPaths


def prepare_source(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    paths.source_background.parent.mkdir(parents=True)
    paths.source_background.write_bytes(b"new background")
    return paths


def test_reconcile_installs_background_and_autostart(tmp_path) -> None:
    paths = prepare_source(tmp_path)

    assert desktop_setup_needs_reconcile(paths, True) is True

    reconcile_desktop_setup(paths, True)

    assert paths.base_background.read_bytes() == b"new background"
    assert paths.wallpaper_autostart.read_bytes() == AUTOSTART_CONTENT
    assert desktop_setup_needs_reconcile(paths, True) is False


def test_reconcile_removes_autostart_when_disabled(tmp_path) -> None:
    paths = prepare_source(tmp_path)
    reconcile_desktop_setup(paths, True)

    reconcile_desktop_setup(paths, False)

    assert not paths.wallpaper_autostart.exists()
    assert paths.base_background.exists()
    assert desktop_setup_needs_reconcile(paths, False) is False


def test_enabled_setup_requires_source_asset(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)

    with pytest.raises(DesktopSetupError, match="Could not read wallpaper asset"):
        desktop_setup_needs_reconcile(paths, True)
