"""Validated classroom VS Code profiles and resolved manifest snapshots."""

import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit
from urllib.request import urlopen

import yaml

MAX_PROFILE_BYTES = 256 * 1024
EXTENSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*\.[A-Za-z0-9][A-Za-z0-9._-]*")


def validate_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("vscode.config_url must be an HTTPS URL")
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError("vscode.config_url must be an HTTPS URL without credentials or fragment")
    return value


def validate_profile(value: object) -> dict:
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError("VS Code profile must have schema: 1")
    if set(value) - {"schema", "folder", "extensions", "disabled_extensions", "settings", "runtime"}:
        raise ValueError("Unknown VS Code profile field")
    folder = value.get("folder", "/home/jam/jam-day")
    if (not isinstance(folder, str) or not folder.startswith("/home/jam/")
            or ".." in PurePosixPath(folder).parts or any(c in folder for c in '\n\r\0')
            or str(PurePosixPath(folder)) != folder):
        raise ValueError("VS Code folder must be a normalized path beneath /home/jam")
    extensions = value.get("extensions", [])
    if not isinstance(extensions, list) or not all(
        isinstance(item, str) and EXTENSION.fullmatch(item) for item in extensions
    ):
        raise ValueError("VS Code extensions must be publisher.extension IDs")
    disabled = value.get("disabled_extensions", [])
    if not isinstance(disabled, list) or not all(
        isinstance(item, str) and EXTENSION.fullmatch(item) for item in disabled
    ):
        raise ValueError("VS Code disabled_extensions must be publisher.extension IDs")
    if {item.lower() for item in extensions} & {item.lower() for item in disabled}:
        raise ValueError("VS Code extensions cannot be both required and disabled")
    settings = value.get("settings", {})
    if not isinstance(settings, dict) or not all(isinstance(key, str) for key in settings):
        raise ValueError("VS Code settings must be a mapping of string keys")
    # YAML dates/sets and non-finite numbers are not VS Code JSON settings.
    json.dumps(settings, allow_nan=False)
    if settings.get("python.defaultInterpreterPath", "/data/nirj/python-venv/bin/python") != "/data/nirj/python-venv/bin/python":
        raise ValueError("VS Code profile must retain the managed Python interpreter")
    runtime = value.get("runtime", {"password-store": "basic"})
    if not isinstance(runtime, dict) or set(runtime) - {"password-store"}:
        raise ValueError("VS Code runtime supports only password-store")
    if runtime.get("password-store", "basic") not in ("basic", "gnome-libsecret"):
        raise ValueError("Unsupported VS Code password-store")
    return {"schema": 1, "folder": folder,
            "extensions": list(dict.fromkeys(item.lower() for item in extensions)),
            "disabled_extensions": list(dict.fromkeys(item.lower() for item in disabled)),
            "settings": settings, "runtime": runtime}


def resolve_profile(content: bytes, source: str, opener=None) -> bytes:
    """Download first, then embed the validated profile in a single cached snapshot."""
    from .parser import ManifestError, parse_manifest

    manifest = parse_manifest(content, source)
    if manifest.vscode_config_url is None:
        return content
    try:
        with (opener or urlopen)(manifest.vscode_config_url, timeout=20) as response:
            raw = response.read(MAX_PROFILE_BYTES + 1)
        if len(raw) > MAX_PROFILE_BYTES:
            raise ValueError("VS Code profile exceeds 256 KiB")
        profile = validate_profile(yaml.safe_load(raw.decode("utf-8")))
        data = yaml.safe_load(content.decode("utf-8"))
        data["vscode"]["_profile"] = profile
        resolved = json.dumps(data, sort_keys=True, allow_nan=False).encode()
        parse_manifest(resolved, source)
        return resolved
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise ManifestError(f"Unable to resolve VS Code profile from {manifest.vscode_config_url}: {exc}") from exc
