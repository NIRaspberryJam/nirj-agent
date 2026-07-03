import subprocess
from dataclasses import dataclass
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
    def __init__(self, runner: CommandRunner = subprocess.run) -> None:
        self.runner = runner

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

    def disable(self) -> None:
        self._run(["raspi-config", "nonint", "disable_overlayfs"])

    def sync_and_reboot(self) -> None:
        self._run(["sync"])
        self._run(["systemctl", "reboot"])

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
