import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class OverlayError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def __call__(self, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class OverlayStatus:
    active: bool
    configured: bool | None


class OverlayManager:
    def __init__(
        self,
        runner: CommandRunner = subprocess.run,
        cmdline_path: Path = Path("/boot/firmware/cmdline.txt"),
        boot_mount: Path = Path("/boot/firmware"),
    ) -> None:
        self.runner = runner
        self.cmdline_path = cmdline_path
        self.boot_mount = boot_mount

    def status(self) -> OverlayStatus:
        filesystem = self._run(["findmnt", "-n", "-o", "FSTYPE", "/"])
        configured_result = self._run(
            ["raspi-config", "nonint", "get_overlay_now"],
            check=False,
        )
        configured = configured_result.returncode == 0
        return OverlayStatus(
            active=filesystem.stdout.strip() == "overlay",
            configured=configured,
        )

    def enable(self) -> None:
        self._run(["raspi-config", "nonint", "enable_overlayfs"])
        self._ensure_persistent_data_mounts()

    def disable(self) -> None:
        self._normalize_overlayroot_for_raspi_config()
        self._run(["raspi-config", "nonint", "disable_overlayfs"])

    def sync_and_reboot(self) -> None:
        self._run(["sync"])
        self._run(["systemctl", "reboot"])

    def _ensure_persistent_data_mounts(self) -> None:
        self._rewrite_overlayroot(_nonrecursive_overlayroot, required=True)

    def _normalize_overlayroot_for_raspi_config(self) -> None:
        self._rewrite_overlayroot(_plain_overlayroot, required=False)

    def _rewrite_overlayroot(
        self,
        replacement: Callable[[re.Match[str]], str],
        *,
        required: bool,
    ) -> None:
        options = self._run(
            ["findmnt", "-n", "-o", "OPTIONS", str(self.boot_mount)]
        ).stdout.strip().split(",")
        remount_read_only = "ro" in options
        if remount_read_only:
            self._run(["mount", "-o", "remount,rw", str(self.boot_mount)])

        try:
            cmdline = self.cmdline_path.read_text(encoding="utf-8")
            updated, replacements = re.subn(
                r"(?<!\S)overlayroot=tmpfs(?::([^\s]+))?",
                replacement,
                cmdline,
            )
            if required and replacements == 0:
                raise OverlayError(
                    f"{self.cmdline_path} does not contain overlayroot=tmpfs"
                )
            self.cmdline_path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            raise OverlayError(
                f"Could not update {self.cmdline_path}: {exc}"
            ) from exc
        finally:
            if remount_read_only:
                self._run(["mount", "-o", "remount,ro", str(self.boot_mount)])

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(
                args,
                check=check,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise OverlayError(f"Command {' '.join(args)} failed: {detail.strip()}") from exc


def _nonrecursive_overlayroot(match: re.Match[str]) -> str:
    parameters = match.group(1)
    if not parameters:
        return "overlayroot=tmpfs:recurse=0"

    values = parameters.split(",")
    values = [value for value in values if not value.startswith("recurse=")]
    values.append("recurse=0")
    return f"overlayroot=tmpfs:{','.join(values)}"


def _plain_overlayroot(_match: re.Match[str]) -> str:
    return "overlayroot=tmpfs"
