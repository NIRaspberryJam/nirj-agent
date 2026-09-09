import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests import parse_manifest
from nirj_agent.providers import AptProviderError, PipProviderError
from nirj_agent.state import AgentState, load_state, save_state
from nirj_agent.storage.files import read_bytes
from nirj_agent.storage.lock import exclusive_lock
from nirj_agent.storage.paths import AgentPaths

from .desktop_shortcuts import reconcile_desktop_shortcuts
from .python_setup import reconcile_python_setup
from .reconciliation import (
    ReconciliationPlan,
    build_package_plan,
    build_python_package_plan,
)


class ApplyError(RuntimeError):
    pass


class PartialApplyError(ApplyError):
    """Independent operations finished, but the target is not fully applied."""


logger = logging.getLogger(__name__)


class PackageApplyProvider(Protocol):
    def list_installed(self) -> set[str]: ...

    def update(self) -> None: ...

    def install(self, packages: tuple[str, ...]) -> None: ...

    def remove(self, packages: tuple[str, ...]) -> None: ...


class PythonPackageApplyProvider(Protocol):
    def list_installed(self) -> dict[str, str]: ...

    def install(self, requirements: tuple[str, ...]) -> None: ...

    def remove(self, packages: tuple[str, ...]) -> None: ...


@dataclass(frozen=True)
class ApplyResult:
    plan: ReconciliationPlan
    state: AgentState


def apply_manifest(
    paths: AgentPaths,
    package_provider: PackageApplyProvider,
    python_provider: PythonPackageApplyProvider,
    clock: Callable[[], datetime] | None = None,
) -> ApplyResult:
    now = clock or (lambda: datetime.now(timezone.utc))

    with exclusive_lock(paths.apply_lock):
        config = load_config(paths.config)

        if config.device.type is DeviceType.LAPTOP_WINDOWS:
            raise ApplyError(
                "Package application is not supported for Windows devices"
            )

        content = read_bytes(paths.manifest_cache)
        manifest = parse_manifest(content, str(paths.manifest_cache))
        previous_state = load_state(paths.state)

        apt_plan = build_package_plan(
            manifest=manifest,
            installed_packages=package_provider.list_installed(),
            previously_managed_packages=set(previous_state.packages),
        )

        python_plan = build_python_package_plan(
            manifest=manifest,
            installed_packages=python_provider.list_installed(),
            previously_managed_packages={
                name for name, _version in previous_state.python_packages
            },
        )

        plan = ReconciliationPlan(
            apt=apt_plan,
            python=python_plan,
        )

        errors: list[str] = []

        def attempt(operation: Callable[[], None]) -> None:
            try:
                operation()
            except (AptProviderError, PipProviderError) as exc:
                logger.error("Manifest operation failed: %s", exc)
                errors.append(str(exc))

        # APT runs first because python3-venv may itself be a desired APT package.
        if apt_plan.install:
            def install_apt() -> None:
                package_provider.update()
                package_provider.install(apt_plan.install)

            attempt(install_apt)

        if apt_plan.remove:
            attempt(lambda: package_provider.remove(apt_plan.remove))

        apt_packages = apt_plan.desired
        available_packages = set(apt_plan.desired)
        if errors:
            # A failed batch may have partially succeeded. Only observed packages
            # can support shortcuts or be recorded as successfully installed.
            try:
                available_packages = package_provider.list_installed()
                apt_packages = tuple(sorted(
                    available_packages & (set(previous_state.packages) | set(apt_plan.desired))
                ))
            except AptProviderError as exc:
                logger.error("Could not verify APT packages: %s", exc)
                errors.append(str(exc))
                available_packages = set()
                # Retain ownership for a later retry when inventory is unknown.
                apt_packages = tuple(sorted(set(previous_state.packages) | set(apt_plan.desired)))

        python_error_start = len(errors)
        if python_plan.install:
            desired_requirements = tuple(
                f"{name}=={version}"
                for name, version in python_plan.desired
            )
            attempt(lambda: python_provider.install(desired_requirements))

        if python_plan.remove:
            attempt(lambda: python_provider.remove(python_plan.remove))

        python_packages = python_plan.desired
        if len(errors) > python_error_start:
            managed = dict(previous_state.python_packages) | dict(python_plan.desired)
            try:
                installed = python_provider.list_installed()
                python_packages = tuple(sorted(
                    (name, version) for name, version in installed.items() if name in managed
                ))
            except PipProviderError as exc:
                logger.error("Could not verify Python packages: %s", exc)
                errors.append(str(exc))
                python_packages = tuple(sorted(managed.items()))

        reconcile_python_setup(paths)
        required_packages = {"vscode": "code", "sonic-pi": "sonic-pi"}
        shortcuts = tuple(
            shortcut for shortcut in manifest.desktop.shortcuts
            if required_packages[shortcut] in available_packages
        )
        for shortcut in set(manifest.desktop.shortcuts) - set(shortcuts):
            message = f"Skipped {shortcut} shortcut: required package is not confirmed installed"
            logger.error(message)
            errors.append(message)
        reconcile_desktop_shortcuts(paths, shortcuts)

        applied_at = now().astimezone(timezone.utc)
        state = AgentState(
            manifest_hash=previous_state.manifest_hash if errors else hashlib.sha256(content).hexdigest(),
            last_apply=previous_state.last_apply if errors else applied_at.isoformat().replace("+00:00", "Z"),
            packages=apt_packages,
            overlay_enabled=False,
            ready=False,
            python_packages=python_packages,
            errors=tuple(errors),
        )
        save_state(state, paths.state)

        if errors:
            raise PartialApplyError("; ".join(errors))

        return ApplyResult(plan=plan, state=state)
