from nirj_agent.services.desktop_shortcuts import (
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
