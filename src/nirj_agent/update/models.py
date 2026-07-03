from dataclasses import dataclass
from enum import StrEnum


class UpdatePhase(StrEnum):
    NORMAL = "normal"
    PENDING = "pending_update"
    APPLYING = "applying_update"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateState:
    state: UpdatePhase = UpdatePhase.NORMAL
    target_hash: str | None = None
    error: str | None = None
