from nirj_agent.update import (
    UpdatePhase,
    UpdateState,
    load_update_state,
    save_update_state,
)


def test_missing_update_state_is_normal(tmp_path) -> None:
    assert load_update_state(tmp_path / "update.json") == UpdateState()


def test_update_state_round_trip(tmp_path) -> None:
    path = tmp_path / "update.json"
    expected = UpdateState(UpdatePhase.PENDING, "abc123", None)
    save_update_state(expected, path)
    assert load_update_state(path) == expected
