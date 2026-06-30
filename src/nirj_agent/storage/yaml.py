import os
from pathlib import Path
from typing import Any

import yaml


class YamlStoreError(RuntimeError):
    pass


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise YamlStoreError(f"Unable to read {path}: {exc}") from exc

    if value is None:
        return {}

    if not isinstance(value, dict):
        raise YamlStoreError(f"{path} must contain a YAML mapping")

    return value


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(value, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)
    except (OSError, yaml.YAMLError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise YamlStoreError(f"Unable to write {path}: {exc}") from exc
