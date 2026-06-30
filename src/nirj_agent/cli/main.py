import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys
from typing import Sequence

from nirj_agent.config import ConfigError, DeviceType, create_config, load_config
from nirj_agent.manifests.github import GitHubManifestClient, ManifestDownloadError
from nirj_agent.manifests.parser import ManifestError
from nirj_agent.providers import AptProvider, AptProviderError
from nirj_agent.services.manifest import refresh_manifest
from nirj_agent.services.plan import PlanError, create_plan
from nirj_agent.state import load_state
from nirj_agent.storage.files import FileStoreError
from nirj_agent.storage.paths import AgentPaths
from nirj_agent.storage.yaml import YamlStoreError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nirj-agent")
    parser.add_argument(
        "--root",
        type=Path,
        help="use a sandbox filesystem root instead of system paths",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("status")
    subcommands.add_parser("get-config")
    subcommands.add_parser(
        "plan",
        help="show package changes without applying them",
    )

    setup_parser = subcommands.add_parser(
        "setup",
        help="create the initial device configuration",
    )
    setup_parser.add_argument(
        "--device-type",
        required=True,
        choices=[device_type.value for device_type in DeviceType],
    )
    setup_parser.add_argument("--asset-id", required=True)

    manifest_parser = subcommands.add_parser("manifest")
    manifest_commands = manifest_parser.add_subparsers(
        dest="manifest_command",
        required=True,
    )
    manifest_commands.add_parser(
        "refresh",
        help="download, validate and cache the configured manifest",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = AgentPaths.sandbox(args.root) if args.root else AgentPaths.system()

    if args.command == "status":
        state = load_state(paths.state)
        print(json.dumps(asdict(state), indent=2))
        return 0 if state.ready else 1

    if args.command == "get-config":
        config = load_config(paths.config)
        print(json.dumps(asdict(config), indent=2, default=str))
        return 0

    if args.command == "plan":
        try:
            plan = create_plan(
                paths=paths,
                package_provider=AptProvider(),
            )
        except (
            AptProviderError,
            ConfigError,
            ManifestError,
            PlanError,
            YamlStoreError,
        ) as exc:
            print(f"Package planning failed: {exc}", file=sys.stderr)
            return 1

        print(
            json.dumps(
                {
                    "changes_required": plan.changes_required,
                    "install": plan.install,
                    "remove": plan.remove,
                    "unchanged": plan.unchanged,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "setup":
        try:
            config = create_config(
                asset_id=args.asset_id,
                device_type=DeviceType(args.device_type),
                path=paths.config,
            )
        except ConfigError as exc:
            parser.error(str(exc))

        print(json.dumps(asdict(config), indent=2, default=str))
        return 0
    
    if args.command == "manifest" and args.manifest_command == "refresh":
        try:
            config = load_config(paths.config)
            document = refresh_manifest(
                config=config,
                paths=paths,
                client=GitHubManifestClient(),
            )
        except (
            ConfigError,
            ManifestDownloadError,
            ManifestError,
            FileStoreError,
        ) as exc:
            print(f"Manifest refresh failed: {exc}", file=sys.stderr)
            return 1

        print(
            json.dumps(
                {
                    "schema": document.manifest.schema,
                    "sha256": document.sha256,
                    "source": document.source_url,
                    "cache": str(paths.manifest_cache),
                    "packages": len(document.manifest.apt.packages),
                },
                indent=2,
            )
        )
        return 0

    return 2
