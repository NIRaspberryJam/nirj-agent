from dataclasses import asdict
from pathlib import Path

from nirj_agent.storage.paths import STATE_PATH
from nirj_agent.storage.yaml import read_yaml, write_yaml

from .models import AgentState


def load_state(path: Path = STATE_PATH) -> AgentState:
    if not path.exists():
        return AgentState(None, None, (), False, False)

    data = read_yaml(path)
    return AgentState(
        manifest_hash=data.get("manifest_hash"),
        last_apply=data.get("last_apply"),
        packages=tuple(data.get("packages", [])),
        overlay_enabled=bool(data.get("overlay", {}).get("enabled", False)),
        ready=bool(data.get("ready", False)),
    )


def save_state(state: AgentState, path: Path = STATE_PATH) -> None:
    data = asdict(state)
    data["packages"] = list(state.packages)
    data["overlay"] = {"enabled": data.pop("overlay_enabled")}
    write_yaml(path, data)
