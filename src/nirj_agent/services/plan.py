from typing import Protocol

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests import load_manifest
from nirj_agent.state import load_state
from nirj_agent.storage.paths import AgentPaths

from .reconciliation import (
    ReconciliationPlan,
    build_package_plan,
    build_python_package_plan,
)


class PlanError(RuntimeError):
    pass


class InstalledPackageProvider(Protocol):
    def list_installed(self) -> set[str]: ...


class InstalledPythonPackageProvider(Protocol):
    def list_installed(self) -> dict[str, str]: ...


def create_plan(
    paths: AgentPaths,
    package_provider: InstalledPackageProvider,
    python_provider: InstalledPythonPackageProvider,
) -> ReconciliationPlan:
    config = load_config(paths.config)

    if config.device.type is DeviceType.LAPTOP_WINDOWS:
        raise PlanError(
            "Package planning is not supported for Windows devices"
        )

    manifest = load_manifest(paths.manifest_cache)
    state = load_state(paths.state)

    apt_plan = build_package_plan(
        manifest=manifest,
        installed_packages=package_provider.list_installed(),
        previously_managed_packages=set(state.packages),
    )

    python_plan = build_python_package_plan(
        manifest=manifest,
        installed_packages=python_provider.list_installed(),
        previously_managed_packages={
            name for name, _version in state.python_packages
        },
    )

    return ReconciliationPlan(
        apt=apt_plan,
        python=python_plan,
    )
