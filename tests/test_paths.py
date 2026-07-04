from pathlib import Path

from nirj_agent.storage.paths import AgentPaths


def test_system_paths_use_expected_locations() -> None:
    paths = AgentPaths.system()

    assert paths.root == Path("/data/nirj")
    assert paths.config == Path("/data/nirj/config/config.yaml")
    assert paths.state == Path("/data/nirj/state/state.yaml")
    assert paths.current_manifest == Path("/data/nirj/state/current-manifest.json")
    assert paths.target_manifest == Path("/data/nirj/state/target-manifest.json")
    assert paths.update_state == Path("/data/nirj/state/update.json")
    assert paths.overlay_disabled_once_flag == Path(
        "/data/nirj/state/overlay-disabled-once"
    )
    assert paths.apply_lock == Path("/data/nirj/state/apply.lock")
    assert paths.maintenance_flag == Path(
        "/boot/firmware/nirj-maintenance"
    )
    assert paths.source_background == Path(
        "/data/nirj/agent-repo/assets/background-base.png"
    )
    assert paths.wallpaper_autostart == Path(
        "/etc/xdg/autostart/nirj-wallpaper.desktop"
    )
    assert paths.desktop_dir == Path("/home/jam/Desktop")


def test_sandbox_paths_stay_below_root(tmp_path: Path) -> None:
    paths = AgentPaths.sandbox(tmp_path)

    assert paths.config == tmp_path / "data/nirj/config/config.yaml"
    assert paths.state == tmp_path / "data/nirj/state/state.yaml"
    assert paths.overlay_disabled_once_flag == (
        tmp_path / "data/nirj/state/overlay-disabled-once"
    )
    assert paths.apply_lock == tmp_path / "data/nirj/state/apply.lock"
    assert paths.generated_dir == tmp_path / "data/nirj/cache/generated"
    assert paths.maintenance_flag == (
        tmp_path / "boot/firmware/nirj-maintenance"
    )
    assert paths.base_background == (
        tmp_path / "usr/share/nirj-agent/background-base.png"
    )
    assert paths.source_background == (
        tmp_path / "data/nirj/agent-repo/assets/background-base.png"
    )
    assert paths.wallpaper_autostart == (
        tmp_path / "etc/xdg/autostart/nirj-wallpaper.desktop"
    )
    assert paths.desktop_dir == tmp_path / "home/jam/Desktop"


def test_windows_paths_use_program_data_layout() -> None:
    root = Path(r"C:\ProgramData\nirj")
    desktop = Path(r"C:\Users\Public\Desktop")

    paths = AgentPaths.windows(root, desktop)

    assert paths.root == root
    assert paths.config == root / "config/config.yaml"
    assert paths.state == root / "state/state.yaml"
    assert paths.apply_lock == root / "state/apply.lock"
    assert paths.source_background == root / "agent-repo/assets/background-base.png"
    assert paths.desktop_dir == desktop
