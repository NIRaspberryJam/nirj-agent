from pathlib import Path

from nirj_agent.storage.paths import AgentPaths


def test_system_paths_use_expected_locations() -> None:
    paths = AgentPaths.system()

    assert paths.config == Path("/etc/nirj-agent/config.yaml")
    assert paths.state == Path("/var/lib/nirj-agent/state.yaml")
    assert paths.maintenance_flag == Path(
        "/boot/firmware/nirj-maintenance"
    )


def test_sandbox_paths_stay_below_root(tmp_path: Path) -> None:
    paths = AgentPaths.sandbox(tmp_path)

    assert paths.config == tmp_path / "etc/nirj-agent/config.yaml"
    assert paths.state == tmp_path / "var/lib/nirj-agent/state.yaml"
    assert paths.generated_dir == tmp_path / "var/lib/nirj-agent/generated"
    assert paths.maintenance_flag == (
        tmp_path / "boot/firmware/nirj-maintenance"
    )
    assert paths.base_background == (
        tmp_path / "usr/share/nirj-agent/background-base.png"
    )
