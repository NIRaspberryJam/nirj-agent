from types import SimpleNamespace

from PIL import Image

from nirj_agent.config import DeviceType, create_config
from nirj_agent.services.boot import boot_prep
from nirj_agent.services.overlay import OverlayStatus
from nirj_agent.storage.paths import AgentPaths
from nirj_agent.update import UpdatePhase, UpdateState, load_update_state, save_update_state


MANIFEST = b"schema: 1\napt:\n  packages: [git]\n"


class Client:
    def fetch(self, _source):
        return "https://example.test/manifest.yaml", MANIFEST


class Packages:
    def list_installed(self):
        return {"git"}
    def update(self):
        raise AssertionError("not needed")
    def install(self, _packages):
        raise AssertionError("not needed")
    def remove(self, _packages):
        raise AssertionError("not needed")


class Overlay:
    def __init__(self, active):
        self.active = active
        self.events = []
    def status(self):
        return OverlayStatus(self.active, self.active)
    def enable(self):
        self.events.append("enable")
    def disable(self):
        self.events.append("disable")
    def sync_and_reboot(self):
        self.events.append("reboot")


def prepare(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)
    paths.base_background.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), "black").save(paths.base_background)
    return paths


def test_boot_marks_pending_and_disables_active_overlay(tmp_path) -> None:
    paths = prepare(tmp_path)
    overlay = Overlay(active=True)

    result = boot_prep(paths, Client(), Packages(), overlay)

    assert result.reboot_requested is True
    assert overlay.events == ["disable", "reboot"]
    assert load_update_state(paths.update_state).state is UpdatePhase.PENDING
    assert paths.target_manifest.read_bytes() == MANIFEST


def test_writable_boot_applies_target_and_reenables_overlay(tmp_path) -> None:
    paths = prepare(tmp_path)
    paths.target_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.target_manifest.write_bytes(MANIFEST)
    save_update_state(UpdateState(UpdatePhase.PENDING, "target"), paths.update_state)
    overlay = Overlay(active=False)

    result = boot_prep(paths, Client(), Packages(), overlay)

    assert result.action == "update_applied"
    assert result.reboot_requested is True
    assert overlay.events == ["enable", "reboot"]
    assert paths.current_manifest.read_bytes() == MANIFEST
    assert load_update_state(paths.update_state).state is UpdatePhase.NORMAL


def test_overlay_disable_flag_skips_manifest_for_one_boot(tmp_path) -> None:
    paths = prepare(tmp_path)
    paths.current_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.current_manifest.write_bytes(MANIFEST)
    paths.overlay_disabled_once_flag.touch()
    overlay = Overlay(active=False)

    first_result = boot_prep(paths, Client(), Packages(), overlay)

    assert first_result.action == "ready"
    assert first_result.reboot_requested is False
    assert overlay.events == []
    assert not paths.overlay_disabled_once_flag.exists()

    second_result = boot_prep(paths, Client(), Packages(), overlay)

    assert second_result.action == "enabling_overlay"
    assert second_result.reboot_requested is True
    assert overlay.events == ["enable", "reboot"]


def test_overlay_disable_flag_suppresses_restore_after_update(tmp_path) -> None:
    paths = prepare(tmp_path)
    paths.target_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.target_manifest.write_bytes(MANIFEST)
    paths.overlay_disabled_once_flag.touch()
    save_update_state(UpdateState(UpdatePhase.PENDING, "target"), paths.update_state)
    overlay = Overlay(active=False)

    result = boot_prep(paths, Client(), Packages(), overlay)

    assert result.action == "update_applied"
    assert result.reboot_requested is False
    assert overlay.events == []
    assert not paths.overlay_disabled_once_flag.exists()


def test_overlay_disable_flag_survives_intermediate_reboot(tmp_path) -> None:
    paths = prepare(tmp_path)
    paths.target_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.target_manifest.write_bytes(MANIFEST)
    paths.overlay_disabled_once_flag.touch()
    save_update_state(UpdateState(UpdatePhase.PENDING, "target"), paths.update_state)
    overlay = Overlay(active=True)

    result = boot_prep(paths, Client(), Packages(), overlay)

    assert result.action == "waiting_for_writable_boot"
    assert result.reboot_requested is True
    assert overlay.events == ["disable", "reboot"]
    assert paths.overlay_disabled_once_flag.exists()
