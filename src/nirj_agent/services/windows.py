import hashlib
from collections.abc import Callable
from datetime import datetime, timezone

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests import Manifest
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.manifests.parser import parse_manifest
from nirj_agent.state import AgentState, save_state
from nirj_agent.storage.files import write_bytes
from nirj_agent.storage.lock import exclusive_lock
from nirj_agent.storage.paths import AgentPaths


class WindowsReconcileError(RuntimeError):
    pass


def reconcile_windows(
    paths: AgentPaths,
    client: GitHubManifestClient,
    clock: Callable[[], datetime] | None = None,
) -> AgentState:
    with exclusive_lock(paths.apply_lock):
        config = load_config(paths.config)
        if config.device.type is not DeviceType.LAPTOP_WINDOWS:
            raise WindowsReconcileError(
                "Windows reconciliation requires an lpt-win device"
            )

        source, content = client.fetch(config.manifest)
        manifest = parse_manifest(content, source)
        unsupported = _unsupported_settings(manifest)
        if unsupported:
            fields = ", ".join(unsupported)
            raise WindowsReconcileError(
                f"Windows manifest contains unsupported settings: {fields}"
            )

        digest = hashlib.sha256(content).hexdigest()
        write_bytes(paths.target_manifest, content)
        write_bytes(paths.current_manifest, content)

        now = clock or (lambda: datetime.now(timezone.utc))
        applied_at = now().astimezone(timezone.utc)
        state = AgentState(
            manifest_hash=digest,
            last_apply=applied_at.isoformat().replace("+00:00", "Z"),
            packages=(),
            overlay_enabled=False,
            ready=True,
        )
        save_state(state, paths.state)
        return state


def _unsupported_settings(manifest: Manifest) -> tuple[str, ...]:
    unsupported = []
    if manifest.apt.enforce:
        unsupported.append("apt.enforce")
    if manifest.apt.packages:
        unsupported.append("apt.packages")
    if manifest.desktop.shortcuts:
        unsupported.append("desktop.shortcuts")
    if manifest.overlay_enabled:
        unsupported.append("overlay.enabled")
    if manifest.background_enabled:
        unsupported.append("background.enabled")
    return tuple(unsupported)
