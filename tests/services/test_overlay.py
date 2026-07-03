from types import SimpleNamespace

from nirj_agent.services.overlay import OverlayManager


def test_overlay_status_uses_findmnt_and_raspi_config() -> None:
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        output = "overlay\n" if args[0] == "findmnt" else ""
        return SimpleNamespace(returncode=0, stdout=output)

    status = OverlayManager(run).status()

    assert status.active is True
    assert status.configured is True
    assert calls[0][0] == ["findmnt", "-n", "-o", "FSTYPE", "/"]
    assert calls[1][0] == ["raspi-config", "nonint", "get_overlay_now"]


def test_overlay_transitions_and_reboot_commands() -> None:
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="")

    manager = OverlayManager(run)
    manager.disable()
    manager.enable()
    manager.sync_and_reboot()

    assert calls == [
        ["raspi-config", "nonint", "disable_overlayfs"],
        ["raspi-config", "nonint", "enable_overlayfs"],
        ["sync"],
        ["systemctl", "reboot"],
    ]
