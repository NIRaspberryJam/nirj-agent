from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .models import AptManifest, Manifest

class ManifestError(ValueError):
    pass

def parse_manifest(content: bytes, source: str = "<memory>") -> Manifest:
    try:
        text = content.decode("utf-8")
        data = yaml.safe_load(text)
    except UnicodeDecodeError as exc:
        raise ManifestError(
            f"Manifest from {source} is not valid UTF-8: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise ManifestError(
            f"Manifest from {source} contains invalid YAML: {exc}"
        ) from exc

    return manifest_from_mapping(data, source)

def load_manifest(path: Path) -> Manifest:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ManifestError(f"Unable to read manifest {path}: {exc}") from exc

    return parse_manifest(content, str(path))

    
    
def manifest_from_mapping(data: object, source: str) -> Manifest:
    root = require_mapping(data, "manifest", source)

    schema = root.get("schema")

    if isinstance(schema, bool) or not isinstance(schema, int):
        raise ManifestError(
            f"Manifest from {source} must define schema as an integer"
        )

    if schema != 1:
        raise ManifestError(
            f"Unsupported manifest schema from {source}: {schema}"
        )
    
    apt = require_mapping(root.get("apt", {}), "apt", source)
    packages = apt.get("packages", [])

    if not isinstance(packages, list) or not all(
        isinstance(package, str) and bool(package.strip())
        for package in packages
    ):
        raise ManifestError(
            f"apt.packages in {source} must be a list of package names"
        )
    
    return Manifest(
        schema=schema,
        apt=AptManifest(
            enforce=read_boolean(apt, "enforce", False, source),
            packages=tuple(dict.fromkeys(packages)),
        ),
        overlay_enabled=read_enabled_section(root, "overlay", source),
        background_enabled=read_enabled_section(
            root,
            "background",
            source,
        ),
    )

def require_mapping(
    value: object,
    field: str,
    source: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestError(
            f"{field} in {source} must be a YAML mapping"
        )

    return value


def read_boolean(
    mapping: Mapping[str, Any],
    field: str,
    default: bool,
    source: str,
) -> bool:
    value = mapping.get(field, default)

    if not isinstance(value, bool):
        raise ManifestError(
            f"{field} in {source} must be true or false"
        )

    return value


def read_enabled_section(
    root: Mapping[str, Any],
    section_name: str,
    source: str,
) -> bool:
    section = require_mapping(
        root.get(section_name, {}),
        section_name,
        source,
    )

    return read_boolean(
        section,
        "enabled",
        False,
        source,
    )