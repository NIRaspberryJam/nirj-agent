from dataclasses import asdict
from pathlib import Path

from nirj_agent.storage.json import read_json, write_json
from nirj_agent.storage.paths import SYSTEM_PATHS

from .models import UpdatePhase, UpdateState


def load_update_state(path: Path = SYSTEM_PATHS.update_state) -> UpdateState:
    if not path.exists():
        return UpdateState()
    data = read_json(path)
    return UpdateState(
        state=UpdatePhase(str(data.get("state", UpdatePhase.NORMAL))),
        target_hash=data.get("target_hash"),
        error=data.get("error"),
    )


def save_update_state(
    state: UpdateState,
    path: Path = SYSTEM_PATHS.update_state,
) -> None:
    data = asdict(state)
    data["state"] = state.state.value
    write_json(path, data)
