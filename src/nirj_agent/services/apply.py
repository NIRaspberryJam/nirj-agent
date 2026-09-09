import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests import parse_manifest
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

        # APT runs first because python3-venv may itself be a desired APT package.
        if apt_plan.install:
            package_provider.update()
            package_provider.install(apt_plan.install)

        if apt_plan.remove:
            package_provider.remove(apt_plan.remove)

        if python_plan.install:
            desired_requirements = tuple(
                f"{name}=={version}"
                for name, version in python_plan.desired
            )
            python_provider.install(desired_requirements)

        if python_plan.remove:
            python_provider.remove(python_plan.remove)

        reconcile_python_setup(paths)
        reconcile_desktop_shortcuts(paths, manifest.desktop.shortcuts)

        applied_at = now().astimezone(timezone.utc)
        state = AgentState(
            manifest_hash=hashlib.sha256(content).hexdigest(),
            last_apply=applied_at.isoformat().replace("+00:00", "Z"),
            packages=apt_plan.desired,
            overlay_enabled=False,
            ready=False,
            python_packages=python_plan.desired,
        )
        save_state(state, paths.state)

        return ApplyResult(plan=plan, state=state)
