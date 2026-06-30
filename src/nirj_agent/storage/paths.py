from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentPaths:
    config: Path
    state: Path
    manifest_cache: Path
    apply_lock: Path
    generated_dir: Path
    maintenance_flag: Path
    base_background: Path

    @classmethod
    def system(cls) -> "AgentPaths":
        return cls(
            config=Path("/etc/nirj-agent/config.yaml"),
            state=Path("/var/lib/nirj-agent/state.yaml"),
            manifest_cache=Path(
                "/var/lib/nirj-agent/manifests/current.yaml"
            ),
            apply_lock=Path("/run/nirj-agent/apply.lock"),
            generated_dir=Path("/var/lib/nirj-agent/generated"),
            maintenance_flag=Path("/boot/firmware/nirj-maintenance"),
            base_background=Path(
                "/usr/share/nirj-agent/background-base.png"
            ),
        )

    @classmethod
    def sandbox(cls, root: Path) -> "AgentPaths":
        return cls(
            config=root / "etc/nirj-agent/config.yaml",
            state=root / "var/lib/nirj-agent/state.yaml",
            manifest_cache=(
                root / "var/lib/nirj-agent/manifests/current.yaml"
            ),
            apply_lock=root / "run/nirj-agent/apply.lock",
            generated_dir=root / "var/lib/nirj-agent/generated",
            maintenance_flag=root / "boot/firmware/nirj-maintenance",
            base_background=(
                root / "usr/share/nirj-agent/background-base.png"
            ),
        )


SYSTEM_PATHS = AgentPaths.system()

CONFIG_PATH = SYSTEM_PATHS.config
STATE_PATH = SYSTEM_PATHS.state
MANIFEST_CACHE_PATH = SYSTEM_PATHS.manifest_cache
APPLY_LOCK_PATH = SYSTEM_PATHS.apply_lock
GENERATED_DIR = SYSTEM_PATHS.generated_dir
MAINTENANCE_FLAG_PATH = SYSTEM_PATHS.maintenance_flag
BASE_BACKGROUND_PATH = SYSTEM_PATHS.base_background
