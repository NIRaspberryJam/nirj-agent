from types import SimpleNamespace

import pytest

from nirj_agent.services.overlay import OverlayError, OverlayManager


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


def test_overlay_transitions_and_reboot_commands(tmp_path) -> None:
    calls = []
    cmdline = tmp_path / "cmdline.txt"
    cmdline.write_text("quiet overlayroot=tmpfs:recurse=0 rootwait\n")

    def run(args, **kwargs):
        calls.append(args)
        if args[-1] == "disable_overlayfs":
            assert "overlayroot=tmpfs:recurse=0" not in cmdline.read_text()
            assert "overlayroot=tmpfs" in cmdline.read_text()
        output = "ro,relatime\n" if args[0] == "findmnt" else ""
        return SimpleNamespace(returncode=0, stdout=output)

    manager = OverlayManager(
        run,
        cmdline_path=cmdline,
        boot_mount=tmp_path,
    )
    manager.disable()
    manager.enable()
    manager.sync_and_reboot()

    assert calls == [
        ["findmnt", "-n", "-o", "OPTIONS", str(tmp_path)],
        ["mount", "-o", "remount,rw", str(tmp_path)],
        ["mount", "-o", "remount,ro", str(tmp_path)],
        ["raspi-config", "nonint", "disable_overlayfs"],
        ["raspi-config", "nonint", "enable_overlayfs"],
        ["findmnt", "-n", "-o", "OPTIONS", str(tmp_path)],
        ["mount", "-o", "remount,rw", str(tmp_path)],
        ["mount", "-o", "remount,ro", str(tmp_path)],
        ["sync"],
        ["systemctl", "reboot"],
    ]
    assert cmdline.read_text() == (
        "quiet overlayroot=tmpfs:recurse=0 rootwait\n"
    )


def test_overlay_disable_allows_missing_overlayroot_token(tmp_path) -> None:
    calls = []
    cmdline = tmp_path / "cmdline.txt"
    cmdline.write_text("quiet rootwait\n")

    def run(args, **kwargs):
        calls.append(args)
        output = "rw,relatime\n" if args[0] == "findmnt" else ""
        return SimpleNamespace(returncode=0, stdout=output)

    OverlayManager(
        run,
        cmdline_path=cmdline,
        boot_mount=tmp_path,
    ).disable()

    assert calls[-1] == ["raspi-config", "nonint", "disable_overlayfs"]
    assert cmdline.read_text() == "quiet rootwait\n"


def test_overlay_enable_preserves_parameters_on_writable_boot(tmp_path) -> None:
    calls = []
    cmdline = tmp_path / "cmdline.txt"
    cmdline.write_text("overlayroot=tmpfs:swap=1,recurse=1 quiet\n")

    def run(args, **kwargs):
        calls.append(args)
        output = "rw,relatime\n" if args[0] == "findmnt" else ""
        return SimpleNamespace(returncode=0, stdout=output)

    OverlayManager(
        run,
        cmdline_path=cmdline,
        boot_mount=tmp_path,
    ).enable()

    assert cmdline.read_text() == (
        "overlayroot=tmpfs:swap=1,recurse=0 quiet\n"
    )
    assert all(args[0] != "mount" for args in calls)


def test_overlay_enable_fails_if_raspi_config_does_not_set_cmdline(
    tmp_path,
) -> None:
    calls = []
    cmdline = tmp_path / "cmdline.txt"
    cmdline.write_text("quiet rootwait\n")

    def run(args, **kwargs):
        calls.append(args)
        output = "ro,relatime\n" if args[0] == "findmnt" else ""
        return SimpleNamespace(returncode=0, stdout=output)

    manager = OverlayManager(
        run,
        cmdline_path=cmdline,
        boot_mount=tmp_path,
    )

    with pytest.raises(OverlayError, match="does not contain overlayroot=tmpfs"):
        manager.enable()

    assert calls[-1] == ["mount", "-o", "remount,ro", str(tmp_path)]
