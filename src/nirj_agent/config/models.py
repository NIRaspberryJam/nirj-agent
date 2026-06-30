from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class DeviceType(StrEnum):
    PI5 = "pi5"
    LAPTOP_LINUX = "lpt-lx"
    LAPTOP_WINDOWS = "lpt-win"


@dataclass(frozen=True)
class ManifestSource:
    type: str
    repo: str
    path: str
    ref: str = "main"


@dataclass(frozen=True)
class DeviceConfig:
    id: UUID
    asset_id: str
    type: DeviceType


@dataclass(frozen=True)
class AgentConfig:
    device: DeviceConfig
    manifest: ManifestSource
    overlay_enabled: bool
    background_enabled: bool
