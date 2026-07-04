import argparse
import json
import os
import signal
import sys
from dataclasses import asdict
from pathlib import Path
from threading import Event
from typing import Sequence

import yaml

from nirj_agent.config import (
    ConfigError,
    DeviceType,
    create_config,
    get_config_value,
    load_config,
    set_config_value,
)
from nirj_agent.manifests.github import GitHubManifestClient, ManifestDownloadError
from nirj_agent.manifests.parser import ManifestError
from nirj_agent.providers import AptProvider, AptProviderError
from nirj_agent.services.apply import ApplyError, apply_manifest
from nirj_agent.services.boot import boot_prep
from nirj_agent.services.desktop import (
    DesktopWallpaperError,
    DesktopWallpaperManager,
)
from nirj_agent.services.desktop_setup import DesktopSetupError
from nirj_agent.services.manifest import refresh_manifest
from nirj_agent.services.overlay import OverlayError, OverlayManager
from nirj_agent.services.plan import PlanError, create_plan
from nirj_agent.services.runner import run_agent
from nirj_agent.services.update import check_for_update
from nirj_agent.services.wallpaper import WallpaperError
from nirj_agent.services.wallpaper_session import watch_wallpaper
from nirj_agent.state import load_state
from nirj_agent.storage.files import FileStoreError
from nirj_agent.storage.json import JsonStoreError
from nirj_agent.storage.lock import LockError
from nirj_agent.storage.paths import AgentPaths
from nirj_agent.storage.yaml import YamlStoreError


EXPECTED_ERRORS = (
    ApplyError,
    AptProviderError,
    ConfigError,
    FileStoreError,
    JsonStoreError,
    LockError,
    ManifestDownloadError,
    ManifestError,
    OverlayError,
    PlanError,
    DesktopWallpaperError,
    DesktopSetupError,
    WallpaperError,
    YamlStoreError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nirj-agent")
    parser.add_argument("--root", type=Path, help="use a sandbox filesystem root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("get-config", help=argparse.SUPPRESS)
    commands.add_parser("up", help="start the long-running agent")
    commands.add_parser("boot-prep", help="perform boot-time update preparation")
    commands.add_parser("plan", help="show package changes without applying them")
    commands.add_parser("apply", help="apply the cached target manifest")

    setup = commands.add_parser("setup")
    setup.add_argument("--device-type", required=True, choices=[v.value for v in DeviceType])
    setup.add_argument("--asset-id", required=True)

    manifest = commands.add_parser("manifest")
    manifest_commands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_commands.add_parser("refresh")

    update = commands.add_parser("update")
    update_commands = update.add_subparsers(dest="update_command", required=True)
    update_commands.add_parser("check")
    update_commands.add_parser("apply")

    overlay = commands.add_parser("overlay")
    overlay_commands = overlay.add_subparsers(dest="overlay_command", required=True)
    overlay_commands.add_parser("status")
    overlay_commands.add_parser("enable")
    overlay_commands.add_parser("disable")

    wallpaper = commands.add_parser("wallpaper")
    wallpaper_commands = wallpaper.add_subparsers(
        dest="wallpaper_command",
        required=True,
    )
    wallpaper_commands.add_parser("watch")

    config = commands.add_parser("config")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_get = config_commands.add_parser("get")
    config_get.add_argument("key", nargs="?")
    config_set = config_commands.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = AgentPaths.sandbox(args.root) if args.root else AgentPaths.system()

    try:
        if args.command == "status":
            state = load_state(paths.state)
            print(json.dumps(asdict(state), indent=2))
            return 0 if state.ready else 1

        if args.command == "get-config" or (
            args.command == "config" and args.config_command == "get" and args.key is None
        ):
            print(json.dumps(asdict(load_config(paths.config)), indent=2, default=str))
            return 0

        if args.command == "config" and args.config_command == "get":
            print(json.dumps(get_config_value(args.key, paths.config), default=str))
            return 0

        if args.command == "config" and args.config_command == "set":
            if not _require_root(args.root, "Configuration changes"):
                return 1
            value = yaml.safe_load(args.value)
            if isinstance(value, (dict, list)):
                raise ConfigError("Configuration values must be scalar")
            set_config_value(args.key, value, paths.config)
            print(json.dumps({"key": args.key, "value": value}, default=str))
            return 0

        if args.command == "setup":
            config = create_config(args.asset_id, DeviceType(args.device_type), paths.config)
            print(json.dumps(asdict(config), indent=2, default=str))
            return 0

        if args.command == "up":
            if not _require_root(args.root, "Agent startup"):
                return 1
            return _run_forever(paths)

        if args.command == "boot-prep":
            if not _require_root(args.root, "Boot preparation"):
                return 1
            result = boot_prep(
                paths=paths,
                client=GitHubManifestClient(),
                package_provider=AptProvider(),
                overlay=OverlayManager(),
            )
            print(json.dumps(asdict(result), indent=2))
            return 194 if result.reboot_requested else 0

        if args.command == "update" and args.update_command == "check":
            check = check_for_update(paths=paths, client=GitHubManifestClient())
            print(json.dumps(asdict(check), indent=2))
            return 0

        if args.command == "update" and args.update_command == "apply":
            if not _require_root(args.root, "Update application"):
                return 1
            result = boot_prep(
                paths=paths,
                client=GitHubManifestClient(),
                package_provider=AptProvider(),
                overlay=OverlayManager(),
            )
            print(json.dumps(asdict(result), indent=2))
            return 194 if result.reboot_requested else 0

        if args.command == "overlay":
            manager = OverlayManager()
            if args.overlay_command == "status":
                print(json.dumps(asdict(manager.status()), indent=2))
                return 0
            if not _require_root(args.root, "Overlay changes"):
                return 1
            if args.overlay_command == "disable":
                paths.overlay_disabled_once_flag.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                paths.overlay_disabled_once_flag.touch()
            elif args.overlay_command == "enable":
                paths.overlay_disabled_once_flag.unlink(missing_ok=True)
            getattr(manager, args.overlay_command)()
            manager.sync_and_reboot()
            return 0

        if args.command == "wallpaper" and args.wallpaper_command == "watch":
            return _watch_wallpaper(paths)

        if args.command == "plan":
            plan = create_plan(paths=paths, package_provider=AptProvider())
            print(json.dumps({
                "changes_required": plan.changes_required,
                "install": plan.install,
                "remove": plan.remove,
                "unchanged": plan.unchanged,
            }, indent=2))
            return 0

        if args.command == "apply":
            if not _require_root(args.root, "Package application"):
                return 1
            result = apply_manifest(paths=paths, package_provider=AptProvider())
            print(json.dumps({
                "manifest_hash": result.state.manifest_hash,
                "last_apply": result.state.last_apply,
                "install": result.plan.install,
                "remove": result.plan.remove,
                "ready": result.state.ready,
            }, indent=2))
            return 0

        if args.command == "manifest" and args.manifest_command == "refresh":
            document = refresh_manifest(
                config=load_config(paths.config),
                paths=paths,
                client=GitHubManifestClient(),
            )
            print(json.dumps({
                "schema": document.manifest.schema,
                "sha256": document.sha256,
                "source": document.source_url,
                "cache": str(paths.manifest_cache),
                "packages": len(document.manifest.apt.packages),
            }, indent=2))
            return 0
    except EXPECTED_ERRORS as exc:
        print(f"{_operation_name(args)} failed: {exc}", file=sys.stderr)
        return 1
    return 2


def _require_root(root: Path | None, operation: str) -> bool:
    if root is not None:
        print(f"{operation} does not support --root", file=sys.stderr)
        return False
    if os.geteuid() != 0:
        print(f"{operation} must run as root", file=sys.stderr)
        return False
    return True


def _run_forever(paths: AgentPaths) -> int:
    stop_event = Event()
    def request_shutdown(_signum, _frame) -> None:
        stop_event.set()
    previous_sigint = signal.signal(signal.SIGINT, request_shutdown)
    previous_sigterm = signal.signal(signal.SIGTERM, request_shutdown)
    try:
        run_agent(paths=paths, stop_event=stop_event)
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0


def _watch_wallpaper(paths: AgentPaths) -> int:
    stop_event = Event()

    def request_shutdown(_signum, _frame) -> None:
        stop_event.set()

    previous_sigint = signal.signal(signal.SIGINT, request_shutdown)
    previous_sigterm = signal.signal(signal.SIGTERM, request_shutdown)
    try:
        watch_wallpaper(
            paths=paths,
            stop_event=stop_event,
            desktop=DesktopWallpaperManager(),
        )
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0


def _operation_name(args) -> str:
    names = {
        "apply": "Package application",
        "plan": "Package planning",
        "manifest": "Manifest refresh",
        "boot-prep": "Boot preparation",
        "up": "Agent startup",
        "update": "Update",
        "overlay": "Overlay operation",
        "config": "Configuration operation",
        "setup": "Setup",
        "wallpaper": "Wallpaper operation",
    }
    return names.get(args.command, args.command.capitalize())
