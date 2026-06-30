import subprocess
from collections.abc import Callable
from typing import Any


class AptProviderError(RuntimeError):
    pass


class AptProvider:
    def __init__(
        self,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.runner = runner

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
