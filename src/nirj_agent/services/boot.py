from dataclasses import dataclass, replace

from nirj_agent.config import load_config
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.providers import AptProvider
from nirj_agent.state import load_state, save_state
from nirj_agent.storage.paths import AgentPaths
from nirj_agent.update import (
    UpdatePhase,
    UpdateState,
    load_update_state,
    save_update_state,
)

from .overlay import OverlayManager
from .update import apply_target, check_for_update
from .wallpaper import set_wallpaper_state


@dataclass(frozen=True)
class BootPrepResult:
    action: str
    reboot_requested: bool


def boot_prep(
    paths: AgentPaths,
    client: GitHubManifestClient,
    package_provider: AptProvider,
    overlay: OverlayManager,
) -> BootPrepResult:
    target_hash = None
    try:
        config = load_config(paths.config)
        update = load_update_state(paths.update_state)
        target_hash = update.target_hash
        overlay_status = overlay.status()

        if update.state is UpdatePhase.PENDING:
            if overlay_status.active:
                overlay.disable()
                overlay.sync_and_reboot()
                return BootPrepResult("waiting_for_writable_boot", True)
            return _apply_and_restore(paths, config.overlay_enabled, package_provider, overlay)

        check = check_for_update(paths, client, persist_target=True)
        if check.update_available:
            save_update_state(
                UpdateState(UpdatePhase.PENDING, check.target_hash),
                paths.update_state,
            )
            target_hash = check.target_hash
            set_wallpaper_state(paths, "updating")
            if overlay_status.active:
                overlay.disable()
                overlay.sync_and_reboot()
                return BootPrepResult("update_pending", True)
            return _apply_and_restore(paths, config.overlay_enabled, package_provider, overlay)

        set_wallpaper_state(paths, "ready")
        state = replace(
            load_state(paths.state),
            manifest_hash=check.current_hash,
            overlay_enabled=overlay_status.active,
            ready=True,
        )
        save_state(state, paths.state)
        save_update_state(UpdateState(), paths.update_state)

        if config.overlay_enabled and not overlay_status.active:
            overlay.enable()
            overlay.sync_and_reboot()
            return BootPrepResult("enabling_overlay", True)
        if not config.overlay_enabled and overlay_status.active:
            overlay.disable()
            overlay.sync_and_reboot()
            return BootPrepResult("disabling_overlay", True)
        return BootPrepResult("ready", False)
    except Exception as exc:
        save_update_state(
            UpdateState(UpdatePhase.FAILED, target_hash, str(exc)),
            paths.update_state,
        )
        set_wallpaper_state(paths, "failed")
        raise


def _apply_and_restore(
    paths: AgentPaths,
    overlay_desired: bool,
    package_provider: AptProvider,
    overlay: OverlayManager,
) -> BootPrepResult:
    pending = load_update_state(paths.update_state)
    save_update_state(
        replace(pending, state=UpdatePhase.APPLYING, error=None),
        paths.update_state,
    )
    apply_target(paths, package_provider)
    save_update_state(UpdateState(), paths.update_state)
    set_wallpaper_state(paths, "ready")
    if overlay_desired:
        overlay.enable()
        overlay.sync_and_reboot()
        return BootPrepResult("update_applied", True)
    return BootPrepResult("update_applied", False)
