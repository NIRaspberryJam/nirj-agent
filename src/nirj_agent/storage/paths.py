import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentPaths:
    root: Path
    config: Path
    state: Path
    manifest_cache: Path
    current_manifest: Path
    target_manifest: Path
    update_state: Path
    overlay_disabled_once_flag: Path
    apply_lock: Path
    generated_dir: Path
    maintenance_flag: Path
    base_background: Path
    source_background: Path
    wallpaper_autostart: Path
    desktop_dir: Path

    @classmethod
    def system(cls) -> "AgentPaths":
        if os.name == "nt":
            root = Path(
                os.environ.get(
                    "NIRJ_AGENT_INSTALL_DIR",
                    str(
                        Path(
                            os.environ.get("ProgramData", r"C:\ProgramData")
                        )
                        / "nirj"
                    ),
                )
            )
            public_desktop = (
                Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"
            )
            return cls.windows(root, public_desktop)

        return cls(
            root=Path("/data/nirj"),
            config=Path("/data/nirj/config/config.yaml"),
            state=Path("/data/nirj/state/state.yaml"),
            manifest_cache=Path("/data/nirj/state/target-manifest.json"),
            current_manifest=Path("/data/nirj/state/current-manifest.json"),
            target_manifest=Path("/data/nirj/state/target-manifest.json"),
            update_state=Path("/data/nirj/state/update.json"),
            overlay_disabled_once_flag=Path(
                "/data/nirj/state/overlay-disabled-once"
            ),
            apply_lock=Path("/data/nirj/state/apply.lock"),
            generated_dir=Path("/data/nirj/cache/generated"),
            maintenance_flag=Path("/boot/firmware/nirj-maintenance"),
            base_background=Path(
                "/usr/share/nirj-agent/background-base.png"
            ),
            source_background=Path(
                "/data/nirj/agent-repo/assets/background-base.png"
            ),
            wallpaper_autostart=Path(
                "/etc/xdg/autostart/nirj-wallpaper.desktop"
            ),
            desktop_dir=Path("/home/jam/Desktop"),
        )

    @classmethod
    def windows(cls, root: Path, public_desktop: Path) -> "AgentPaths":
        return cls(
            root=root,
            config=root / "config/config.yaml",
            state=root / "state/state.yaml",
            manifest_cache=root / "state/target-manifest.json",
            current_manifest=root / "state/current-manifest.json",
            target_manifest=root / "state/target-manifest.json",
            update_state=root / "state/update.json",
            overlay_disabled_once_flag=root / "state/overlay-disabled-once",
            apply_lock=root / "state/apply.lock",
            generated_dir=root / "cache/generated",
            maintenance_flag=root / "state/maintenance",
            base_background=root / "assets/background-base.png",
            source_background=root / "agent-repo/assets/background-base.png",
            wallpaper_autostart=root / "config/wallpaper",
            desktop_dir=public_desktop,
        )

    @classmethod
    def sandbox(cls, root: Path) -> "AgentPaths":
        data_root = root / "data/nirj"
        return cls(
            root=data_root,
            config=data_root / "config/config.yaml",
            state=data_root / "state/state.yaml",
            manifest_cache=data_root / "state/target-manifest.json",
            current_manifest=data_root / "state/current-manifest.json",
            target_manifest=data_root / "state/target-manifest.json",
            update_state=data_root / "state/update.json",
            overlay_disabled_once_flag=(
                data_root / "state/overlay-disabled-once"
            ),
            apply_lock=data_root / "state/apply.lock",
            generated_dir=data_root / "cache/generated",
            maintenance_flag=root / "boot/firmware/nirj-maintenance",
            base_background=(
                root / "usr/share/nirj-agent/background-base.png"
            ),
            source_background=(
                data_root / "agent-repo/assets/background-base.png"
            ),
            wallpaper_autostart=(
                root / "etc/xdg/autostart/nirj-wallpaper.desktop"
            ),
            desktop_dir=root / "home/jam/Desktop",
        )


SYSTEM_PATHS = AgentPaths.system()

CONFIG_PATH = SYSTEM_PATHS.config
STATE_PATH = SYSTEM_PATHS.state
MANIFEST_CACHE_PATH = SYSTEM_PATHS.manifest_cache
APPLY_LOCK_PATH = SYSTEM_PATHS.apply_lock
GENERATED_DIR = SYSTEM_PATHS.generated_dir
MAINTENANCE_FLAG_PATH = SYSTEM_PATHS.maintenance_flag
BASE_BACKGROUND_PATH = SYSTEM_PATHS.base_background
