from pathlib import Path
from uuid import UUID, uuid4

from nirj_agent.storage.paths import CONFIG_PATH
from nirj_agent.storage.yaml import read_yaml, write_yaml

from .models import AgentConfig, DeviceConfig, DeviceType, ManifestSource


class ConfigError(ValueError):
    pass


def load_config(path: Path = CONFIG_PATH) -> AgentConfig:
    data = read_yaml(path)

    try:
        device = data["device"]
        source = data["manifest"]["source"]

        return AgentConfig(
            device=DeviceConfig(
                id=UUID(str(device["id"])),
                asset_id=str(device["asset_id"]),
                type=DeviceType(str(device["type"])),
            ),
            manifest=ManifestSource(
                type=str(source["type"]),
                repo=str(source["repo"]),
                path=str(source["path"]),
                ref=str(source.get("ref", "main")),
            ),
            overlay_enabled=bool(
                data.get("overlay", {}).get("enabled", False)
            ),
            background_enabled=bool(
                data.get("background", {}).get("enabled", False)
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid configuration in {path}: {exc}") from exc


def create_config(
    asset_id: str,
    device_type: DeviceType,
    path: Path = CONFIG_PATH,
) -> AgentConfig:
    if path.exists():
        raise ConfigError(
            f"Configuration already exists at {path}; "
            "setup will not replace the device UUID"
        )

    data = {
        "device": {
            "id": str(uuid4()),
            "asset_id": asset_id,
            "type": device_type.value,
        },
        "manifest": {
            "source": {
                "type": "github",
                "repo": "NIRaspberryJam/nirj-infra",
                "path": f"manifests/{device_type.value}.manifest.yaml",
                "ref": "main",
            }
        },
        "overlay": {"enabled": True},
        "background": {"enabled": True},
    }
    write_yaml(path, data)
    return load_config(path)
