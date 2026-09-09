import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from packaging.utils import InvalidName, canonicalize_name
from packaging.version import InvalidVersion, Version

from .models import (
    SUPPORTED_DESKTOP_SHORTCUTS,
    AptManifest,
    DesktopManifest,
    Manifest,
    PythonManifest,
)


PACKAGE_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?$"
)


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
        isinstance(package, str) and PACKAGE_NAME_PATTERN.fullmatch(package)
        for package in packages
    ):
        raise ManifestError(
            f"apt.packages in {source} must be a list of package names"
        )

    python = require_mapping(root.get("python", {}), "python", source)
    raw_python_packages = require_mapping(
        python.get("packages", {}),
        "python.packages",
        source,
    )

    python_packages: dict[str, str] = {}

    for raw_name, raw_version in raw_python_packages.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ManifestError(
                f"python.packages in {source} contains an invalid package name"
            )

        if not isinstance(raw_version, str) or not raw_version.strip():
            raise ManifestError(
                f"Python package {raw_name!r} in {source} must have an "
                "exact version"
            )

        try:
            name = canonicalize_name(raw_name, validate=True)
        except InvalidName as exc:
            raise ManifestError(
                f"python.packages in {source} contains invalid package "
                f"name {raw_name!r}"
            ) from exc

        try:
            version = str(Version(raw_version))
        except InvalidVersion as exc:
            raise ManifestError(
                f"Python package {raw_name!r} in {source} has invalid "
                f"version {raw_version!r}"
            ) from exc

        if name in python_packages:
            raise ManifestError(
                f"python.packages in {source} contains duplicate normalized "
                f"package name {name!r}"
            )

        python_packages[name] = version

    desktop = require_mapping(root.get("desktop", {}), "desktop", source)
    shortcuts = desktop.get("shortcuts", [])

    if not isinstance(shortcuts, list) or not all(
        isinstance(shortcut, str)
        and shortcut in SUPPORTED_DESKTOP_SHORTCUTS
        for shortcut in shortcuts
    ):
        supported = ", ".join(sorted(SUPPORTED_DESKTOP_SHORTCUTS))
        raise ManifestError(
            f"desktop.shortcuts in {source} must be a list containing only: "
            f"{supported}"
        )

    if "vscode" in shortcuts and "code" not in packages:
        raise ManifestError(
            f"desktop shortcut vscode in {source} requires code in "
            "apt.packages"
        )

    if "sonic-pi" in shortcuts and "sonic-pi" not in packages:
        raise ManifestError(
            f"desktop shortcut sonic-pi in {source} requires sonic-pi in "
            "apt.packages"
        )

    return Manifest(
        schema=schema,
        apt=AptManifest(
            enforce=read_boolean(apt, "enforce", False, source),
            packages=tuple(dict.fromkeys(packages)),
        ),
        python=PythonManifest(
            packages=tuple(sorted(python_packages.items())),
        ),
        desktop=DesktopManifest(
            shortcuts=tuple(dict.fromkeys(shortcuts)),
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
