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

from .reconciliation import PackagePlan, build_package_plan


class ApplyError(RuntimeError):
    pass


class PackageApplyProvider(Protocol):
    def list_installed(self) -> set[str]: ...

    def update(self) -> None: ...

    def install(self, packages: tuple[str, ...]) -> None: ...

    def remove(self, packages: tuple[str, ...]) -> None: ...


@dataclass(frozen=True)
class ApplyResult:
    plan: PackagePlan
    state: AgentState


def apply_manifest(
    paths: AgentPaths,
    package_provider: PackageApplyProvider,
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
        installed = package_provider.list_installed()
        plan = build_package_plan(
            manifest=manifest,
            installed_packages=installed,
            previously_managed_packages=set(previous_state.packages),
        )

        if plan.install:
            package_provider.update()
            package_provider.install(plan.install)

        if plan.remove:
            package_provider.remove(plan.remove)

        applied_at = now().astimezone(timezone.utc)
        state = AgentState(
            manifest_hash=hashlib.sha256(content).hexdigest(),
            last_apply=applied_at.isoformat().replace("+00:00", "Z"),
            packages=plan.desired,
            overlay_enabled=False,
            ready=False,
        )
        save_state(state, paths.state)

        return ApplyResult(plan=plan, state=state)
