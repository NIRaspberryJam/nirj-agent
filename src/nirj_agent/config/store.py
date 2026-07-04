from pathlib import Path
from uuid import UUID, uuid4

from nirj_agent.storage.paths import CONFIG_PATH
from nirj_agent.storage.yaml import read_yaml, write_yaml

from .models import AgentConfig, DeviceConfig, DeviceType, ManifestSource


class ConfigError(ValueError):
    pass


def load_config(path: Path = CONFIG_PATH) -> AgentConfig:
    data = read_yaml(path)
    return config_from_mapping(data, path)


def config_from_mapping(data: dict, path: Path) -> AgentConfig:

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


def get_config_value(key: str, path: Path = CONFIG_PATH):
    value = read_yaml(path)
    for part in _key_parts(key):
        if not isinstance(value, dict) or part not in value:
            raise ConfigError(f"Unknown configuration key: {key}")
        value = value[part]
    return value


def set_config_value(key: str, value, path: Path = CONFIG_PATH) -> AgentConfig:
    data = read_yaml(path)
    target = data
    parts = _key_parts(key)
    for part in parts[:-1]:
        if not isinstance(target, dict) or part not in target:
            raise ConfigError(f"Unknown configuration key: {key}")
        target = target[part]
    if not isinstance(target, dict) or parts[-1] not in target:
        raise ConfigError(f"Unknown configuration key: {key}")
    target[parts[-1]] = value
    config = config_from_mapping(data, path)
    write_yaml(path, data)
    return config


def _key_parts(key: str) -> list[str]:
    parts = key.split(".")
    if not key or any(not part for part in parts):
        raise ConfigError(f"Invalid configuration key: {key}")
    return parts


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

    is_windows = device_type is DeviceType.LAPTOP_WINDOWS
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
        "overlay": {"enabled": not is_windows},
        "background": {"enabled": not is_windows},
    }
    write_yaml(path, data)
    return load_config(path)
