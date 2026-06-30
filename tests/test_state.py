from pathlib import Path

from nirj_agent.state import AgentState, load_state, save_state


def test_missing_state_returns_not_ready(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing.yaml")
    assert state == AgentState(
        manifest_hash=None,
        last_apply=None,
        packages=(),
        overlay_enabled=False,
        ready=False,
    )


def test_save_and_load_state(tmp_path: Path) -> None:
    path = tmp_path / "state.yaml"
    expected = AgentState(
        manifest_hash="abc123",
        last_apply="2026-06-29T20:14:00Z",
        packages=("thonny", "scratch"),
        overlay_enabled=True,
        ready=True,
    )
    save_state(expected, path)
    assert load_state(path) == expected
