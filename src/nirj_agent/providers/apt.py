import subprocess
from collections.abc import Callable
from typing import Any


class AptProviderError(RuntimeError):
    pass


class AptProvider:
    def __init__(
        self,
        runner: Callable[..., Any] = subprocess.run,
        command_timeout: int = 1800,
    ) -> None:
        self.runner = runner
        self.command_timeout = command_timeout

    def list_installed(self) -> set[str]:
        try:
            result = self.runner(
                [
                    "dpkg-query",
                    "-W",
                    "-f=${binary:Package}\t${db:Status-Abbrev}\n",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AptProviderError(
                f"Unable to query installed packages: {exc}"
            ) from exc

        if result.returncode != 0:
            error = result.stderr.strip() or "unknown dpkg-query error"
            raise AptProviderError(f"dpkg-query failed: {error}")

        packages: set[str] = set()

        for line in result.stdout.splitlines():
            package, separator, status = line.partition("\t")

            if separator and package and status.startswith("ii"):
                packages.add(package)

        return packages

    def update(self) -> None:
        self._run_apt(["apt-get", "update"], "apt-get update")

    def install(self, packages: tuple[str, ...]) -> None:
        if not packages:
            return

        self._run_apt(
            ["apt-get", "install", "--yes", "--no-remove", "--", *packages],
            "package installation",
        )

    def remove(self, packages: tuple[str, ...]) -> None:
        if not packages:
            return

        self._run_apt(
            ["apt-get", "remove", "--yes", "--", *packages],
            "package removal",
        )

    def _run_apt(self, command: list[str], operation: str) -> None:
        try:
            result = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AptProviderError(f"Unable to run {operation}: {exc}") from exc

        if result.returncode != 0:
            error = result.stderr.strip() or f"exit code {result.returncode}"
            raise AptProviderError(f"{operation} failed: {error}")
