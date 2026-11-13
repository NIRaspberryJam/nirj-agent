from nirj_agent.services.desktop_shortcuts import (
    SONIC_PI_DESKTOP_ENTRY,
    VSCODE_DESKTOP_ENTRY,
    reconcile_desktop_shortcuts,
)
from nirj_agent.storage.paths import AgentPaths


def test_reconcile_creates_executable_vscode_shortcut(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)

    reconcile_desktop_shortcuts(paths, ("vscode",))

    shortcut = paths.desktop_dir / "visual-studio-code.desktop"
    assert shortcut.read_bytes() == VSCODE_DESKTOP_ENTRY
    assert shortcut.stat().st_mode & 0o777 == 0o755


def test_reconcile_removes_unwanted_vscode_shortcut(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    reconcile_desktop_shortcuts(paths, ("vscode",))

    reconcile_desktop_shortcuts(paths, ())

    assert not (paths.desktop_dir / "visual-studio-code.desktop").exists()


def test_reconcile_creates_executable_sonic_pi_shortcut(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)

    reconcile_desktop_shortcuts(paths, ("sonic-pi",))

    shortcut = paths.desktop_dir / "sonic-pi.desktop"
    assert shortcut.read_bytes() == SONIC_PI_DESKTOP_ENTRY
    assert shortcut.stat().st_mode & 0o777 == 0o755


def test_reconcile_removes_unwanted_sonic_pi_shortcut(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    reconcile_desktop_shortcuts(paths, ("sonic-pi",))

    reconcile_desktop_shortcuts(paths, ())

    assert not (paths.desktop_dir / "sonic-pi.desktop").exists()


def test_sonic_pi_menu_override_and_drift(tmp_path) -> None:
    from nirj_agent.services.desktop_shortcuts import desktop_shortcuts_need_reconcile

    paths = AgentPaths.sandbox(tmp_path)
    assert desktop_shortcuts_need_reconcile(paths, ("sonic-pi",))
    reconcile_desktop_shortcuts(paths, ("sonic-pi",))
    menu = paths.applications_dir / "sonic-pi.desktop"
    assert b"Exec=/usr/bin/pw-jack /usr/bin/sonic-pi\n" in menu.read_bytes()
    assert not desktop_shortcuts_need_reconcile(paths, ("sonic-pi",))
    menu.write_bytes(b"stale launcher")
    assert desktop_shortcuts_need_reconcile(paths, ("sonic-pi",))
    reconcile_desktop_shortcuts(paths, ())
    assert not menu.exists()
    assert not desktop_shortcuts_need_reconcile(paths, ())
