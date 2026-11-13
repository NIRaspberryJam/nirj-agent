import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name


class PipProviderError(RuntimeError):
    pass


class PipProvider:
    def __init__(
        self,
        environment: Path,
        runner: Callable[..., Any] = subprocess.run,
        base_python: str = "/usr/bin/python3",
        command_timeout: int = 1800,
    ) -> None:
        self.environment = environment
        self.runner = runner
        self.base_python = base_python
        self.command_timeout = command_timeout

    @property
    def python(self) -> Path:
        return self.environment / "bin/python"

    def list_installed(self) -> dict[str, str]:
        if not self.python.exists():
            return {}

        result = self._run(
            [
                str(self.python),
                "-m",
                "pip",
                "--disable-pip-version-check",
                "list",
                "--format=json",
            ],
            "Python package query",
            timeout=30,
        )

        try:
            packages = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PipProviderError(
                "python package query returned invalid JSON"
            ) from exc

        if not isinstance(packages, list):
            raise PipProviderError(
                "Python package query returned an invalid package list"
            )

        installed: dict[str, str] = {}

        for package in packages:
            if not isinstance(package, dict):
                raise PipProviderError(
                    "Python package query returned an invalid package entry"
                )

            name = package.get("name")
            version = package.get("version")

            if not isinstance(name, str) or not isinstance(version, str):
                raise PipProviderError(
                    "Python package query returned an invalid package entry"
                )

            installed[canonicalize_name(name)] = version

        return installed

    def install(self, requirements: tuple[str, ...]) -> None:
        if not requirements:
            return

        self.ensure_environment()
        self._run(
            [
                str(self.python),
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "--only-binary=:all:",
                *requirements,
            ],
            "Python package installation",
        )

    def remove(self, packages: tuple[str, ...]) -> None:
        if not packages or not self.python.exists():
            return

        self._run(
            [
                str(self.python),
                "-m",
                "pip",
                "--disable-pip-version-check",
                "uninstall",
                "--yes",
                *packages,
            ],
            "Python package removal",
        )

    def ensure_environment(self) -> None:
        if self.python.exists():
            return

        self.environment.parent.mkdir(parents=True, exist_ok=True)

        self._run(
            [
                self.base_python,
                "-m",
                "venv",
                str(self.environment),
            ],
            "Python environment creation",
        )

        if not self.python.exists():
            raise PipProviderError(
                f"Python environment creation did not produce {self.python}"
            )

    def _run(
        self,
        command: list[str],
        operation: str,
        timeout: int | None = None,
    ) -> Any:
        try:
            result = self.runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout or self.command_timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PipProviderError(
                f"Unable to run {operation}: {exc}"
            ) from exc

        if result.returncode != 0:
            error = result.stderr.strip() or f"exit code {result.returncode}"
            raise PipProviderError(f"{operation} failed: {error}")

        return result
