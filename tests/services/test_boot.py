from types import SimpleNamespace

from PIL import Image

from nirj_agent.config import DeviceType, create_config
from nirj_agent.services.boot import boot_prep
from nirj_agent.services.desktop_setup import AUTOSTART_CONTENT
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


class PythonPackages:
    def list_installed(self):
        return {}
    def install(self, _requirements):
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
    paths.source_background.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), "black").save(paths.source_background)
    paths.base_background.parent.mkdir(parents=True)
    paths.base_background.write_bytes(paths.source_background.read_bytes())
    paths.wallpaper_autostart.parent.mkdir(parents=True)
    paths.wallpaper_autostart.write_bytes(AUTOSTART_CONTENT)
    return paths


def test_boot_marks_pending_and_disables_active_overlay(tmp_path) -> None:
    paths = prepare(tmp_path)
    overlay = Overlay(active=True)

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

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

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

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

    first_result = boot_prep(
        paths, Client(), Packages(), PythonPackages(), overlay
    )

    assert first_result.action == "ready"
    assert first_result.reboot_requested is False
    assert overlay.events == []
    assert not paths.overlay_disabled_once_flag.exists()

    second_result = boot_prep(
        paths, Client(), Packages(), PythonPackages(), overlay
    )

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

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

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

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

    assert result.action == "waiting_for_writable_boot"
    assert result.reboot_requested is True
    assert overlay.events == ["disable", "reboot"]
    assert paths.overlay_disabled_once_flag.exists()


def test_desktop_setup_requests_writable_boot_when_overlay_is_active(
    tmp_path,
) -> None:
    paths = prepare(tmp_path)
    paths.wallpaper_autostart.unlink()
    overlay = Overlay(active=True)

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

    assert result.action == "waiting_for_writable_desktop_setup"
    assert result.reboot_requested is True
    assert overlay.events == ["disable", "reboot"]
    assert not paths.wallpaper_autostart.exists()


def test_desktop_setup_is_persisted_on_writable_boot(tmp_path) -> None:
    paths = prepare(tmp_path)
    paths.wallpaper_autostart.unlink()
    paths.base_background.write_bytes(b"old image")
    paths.current_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.current_manifest.write_bytes(MANIFEST)
    overlay = Overlay(active=False)

    result = boot_prep(paths, Client(), Packages(), PythonPackages(), overlay)

    assert result.action == "enabling_overlay"
    assert paths.wallpaper_autostart.read_bytes() == AUTOSTART_CONTENT
    assert (
        paths.base_background.read_bytes()
        == paths.source_background.read_bytes()
    )


def test_partial_package_failure_keeps_agent_startable_and_retries(tmp_path):
    from nirj_agent.config.store import set_config_value
    from nirj_agent.providers import AptProviderError
    from nirj_agent.state import load_state

    paths = prepare(tmp_path)
    set_config_value("overlay.enabled", False, paths.config)
    paths.current_manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.current_manifest.write_bytes(MANIFEST)
    target = (b"schema: 1\napt:\n  packages: [code, git]\n"
              b"python:\n  packages:\n    pyfiglet: '1.0.2'\n"
              b"desktop:\n  shortcuts: [vscode]\n")

    class TargetClient:
        def fetch(self, source):
            return "https://example.test/target.yaml", target

    class Apt:
        installed = {"git"}
        fail = True

        def list_installed(self):
            return self.installed.copy()

        def update(self):
            pass

        def install(self, packages):
            if self.fail:
                raise AptProviderError("Unable to locate package code")
            self.installed.update(packages)

    class Python:
        def __init__(self):
            self.installed = {}
            self.installs = 0

        def list_installed(self):
            return self.installed.copy()

        def install(self, requirements):
            self.installs += 1
            self.installed.update(item.split("==") for item in requirements)

    apt = Apt()
    python = Python()
    overlay = Overlay(False)
    first = boot_prep(paths, TargetClient(), apt, python, overlay)

    assert first.action == "update_failed"
    assert not first.reboot_requested
    assert overlay.events == []
    assert python.installed == {"pyfiglet": "1.0.2"}
    assert not (paths.desktop_dir / "visual-studio-code.desktop").exists()
    assert paths.current_manifest.read_bytes() == MANIFEST
    state = load_state(paths.state)
    assert not state.ready
    assert state.packages == ("git",)
    assert state.python_packages == (("pyfiglet", "1.0.2"),)
    assert "Unable to locate package code" in state.errors
    assert load_update_state(paths.update_state).state is UpdatePhase.FAILED

    apt.fail = False
    second = boot_prep(paths, TargetClient(), apt, python, overlay)

    assert second.action == "update_applied"
    assert paths.current_manifest.read_bytes() == target
    assert (paths.desktop_dir / "visual-studio-code.desktop").exists()
    assert python.installs == 1
    assert load_state(paths.state).ready
    assert not load_state(paths.state).errors
    assert load_update_state(paths.update_state).state is UpdatePhase.NORMAL
