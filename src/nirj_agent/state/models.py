from dataclasses import dataclass


@dataclass(frozen=True)
class AgentState:
    manifest_hash: str | None
    last_apply: str | None
    packages: tuple[str, ...]
    overlay_enabled: bool
    ready: bool
