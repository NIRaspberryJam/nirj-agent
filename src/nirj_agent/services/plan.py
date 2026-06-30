from typing import Protocol

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests import load_manifest
from nirj_agent.state import load_state
from nirj_agent.storage.paths import AgentPaths

from .reconciliation import PackagePlan, build_package_plan


class PlanError(RuntimeError):
    pass


class InstalledPackageProvider(Protocol):
    def list_installed(self) -> set[str]: ...


def create_plan(
    paths: AgentPaths,
    package_provider: InstalledPackageProvider,
) -> PackagePlan:
    config = load_config(paths.config)

    if config.device.type is DeviceType.LAPTOP_WINDOWS:
        raise PlanError(
            "Package planning is not supported for Windows devices"
        )

    manifest = load_manifest(paths.manifest_cache)
    state = load_state(paths.state)
    installed = package_provider.list_installed()

    return build_package_plan(
        manifest=manifest,
        installed_packages=installed,
        previously_managed_packages=set(state.packages),
    )
