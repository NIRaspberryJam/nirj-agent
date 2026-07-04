import logging
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

from .desktop_setup import (
    desktop_setup_needs_reconcile,
    reconcile_desktop_setup,
)
from .overlay import OverlayManager
from .update import apply_target, check_for_update
from .wallpaper import set_wallpaper_state


logger = logging.getLogger(__name__)


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
    config = None
    try:
        config = load_config(paths.config)
        update = load_update_state(paths.update_state)
        target_hash = update.target_hash
        overlay_status = overlay.status()
        overlay_disabled_once = paths.overlay_disabled_once_flag.exists()
        overlay_desired = config.overlay_enabled and not overlay_disabled_once
        desktop_setup_required = desktop_setup_needs_reconcile(
            paths,
            config.background_enabled,
        )

        if desktop_setup_required and overlay_status.active:
            overlay.disable()
            overlay.sync_and_reboot()
            return BootPrepResult("waiting_for_writable_desktop_setup", True)

        if desktop_setup_required:
            reconcile_desktop_setup(paths, config.background_enabled)

        if update.state is UpdatePhase.PENDING:
            if overlay_status.active:
                overlay.disable()
                overlay.sync_and_reboot()
                return BootPrepResult("waiting_for_writable_boot", True)
            result = _apply_and_restore(
                paths,
                overlay_desired,
                config.background_enabled,
                config.device.asset_id,
                package_provider,
                overlay,
            )
            _consume_overlay_disabled_once(paths, overlay_disabled_once)
            return result

        check = check_for_update(paths, client, persist_target=True)
        if check.update_available:
            save_update_state(
                UpdateState(UpdatePhase.PENDING, check.target_hash),
                paths.update_state,
            )
            target_hash = check.target_hash
            _set_wallpaper(
                paths,
                config.background_enabled,
                "updating",
                config.device.asset_id,
            )
            if overlay_status.active:
                overlay.disable()
                overlay.sync_and_reboot()
                return BootPrepResult("update_pending", True)
            result = _apply_and_restore(
                paths,
                overlay_desired,
                config.background_enabled,
                config.device.asset_id,
                package_provider,
                overlay,
            )
            _consume_overlay_disabled_once(paths, overlay_disabled_once)
            return result

        _set_wallpaper(
            paths,
            config.background_enabled,
            "ready",
            config.device.asset_id,
        )
        state = replace(
            load_state(paths.state),
            manifest_hash=check.current_hash,
            overlay_enabled=overlay_status.active,
            ready=True,
        )
        save_state(state, paths.state)
        save_update_state(UpdateState(), paths.update_state)

        if overlay_desired and not overlay_status.active:
            overlay.enable()
            overlay.sync_and_reboot()
            return BootPrepResult("enabling_overlay", True)
        if (
            not overlay_desired
            and not overlay_disabled_once
            and overlay_status.active
        ):
            overlay.disable()
            overlay.sync_and_reboot()
            return BootPrepResult("disabling_overlay", True)
        _consume_overlay_disabled_once(paths, overlay_disabled_once)
        return BootPrepResult("ready", False)
    except Exception as exc:
        save_update_state(
            UpdateState(UpdatePhase.FAILED, target_hash, str(exc)),
            paths.update_state,
        )
        if config is not None:
            _set_wallpaper(
                paths,
                config.background_enabled,
                "failed",
                config.device.asset_id,
            )
        raise


def _apply_and_restore(
    paths: AgentPaths,
    overlay_desired: bool,
    background_enabled: bool,
    asset_code: str,
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
    _set_wallpaper(paths, background_enabled, "ready", asset_code)
    if overlay_desired:
        overlay.enable()
        overlay.sync_and_reboot()
        return BootPrepResult("update_applied", True)
    return BootPrepResult("update_applied", False)


def _set_wallpaper(
    paths: AgentPaths,
    enabled: bool,
    state: str,
    asset_code: str,
) -> None:
    if not enabled:
        return
    try:
        set_wallpaper_state(paths, state, asset_code)
    except Exception:
        logger.exception("Could not set wallpaper state to %s", state)


def _consume_overlay_disabled_once(
    paths: AgentPaths,
    overlay_disabled_once: bool,
) -> None:
    if overlay_disabled_once:
        paths.overlay_disabled_once_flag.unlink()
