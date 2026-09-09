import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from nirj_agent.providers import PipProvider, PipProviderError


def completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
    )


def test_list_installed_returns_empty_when_environment_is_missing(
    tmp_path: Path,
) -> None:
    calls = []
    provider = PipProvider(
        tmp_path / "venv",
        runner=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert provider.list_installed() == {}
    assert calls == []


def test_list_installed_normalizes_package_names(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    python = environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()

    runner = lambda *_args, **_kwargs: completed(
        stdout=json.dumps(
            [
                {"name": "JamKit", "version": "0.1.0"},
                {"name": "example_package", "version": "2.0"},
            ]
        )
    )

    provider = PipProvider(environment, runner=runner)

    assert provider.list_installed() == {
        "jamkit": "0.1.0",
        "example-package": "2.0",
    }


def test_install_creates_environment_and_installs_exact_requirements(
    tmp_path: Path,
) -> None:
    environment = tmp_path / "venv"
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        if command[:3] == ["/usr/bin/python3", "-m", "venv"]:
            python = environment / "bin/python"
            python.parent.mkdir(parents=True)
            python.touch()
        return completed()

    provider = PipProvider(environment, runner=runner)
    provider.install(("jamkit==0.1.0",))

    assert calls[0] == [
        "/usr/bin/python3",
        "-m",
        "venv",
        str(environment),
    ]
    assert calls[1] == [
        str(environment / "bin/python"),
        "-m",
        "pip",
        "--disable-pip-version-check",
        "install",
        "--only-binary=:all:",
        "jamkit==0.1.0",
    ]


def test_remove_uses_environment_python(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    python = environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []

    def runner(command, **_kwargs):
        calls.append(command)
        return completed()

    PipProvider(environment, runner=runner).remove(("obsolete",))

    assert calls == [
        [
            str(python),
            "-m",
            "pip",
            "--disable-pip-version-check",
            "uninstall",
            "--yes",
            "obsolete",
        ]
    ]


def test_command_failure_is_wrapped(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    python = environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()

    provider = PipProvider(
        environment,
        runner=lambda *_args, **_kwargs: completed(
            stderr="network failed",
            returncode=1,
        ),
    )

    with pytest.raises(PipProviderError, match="network failed"):
        provider.list_installed()


def test_timeout_is_wrapped(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    python = environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()

    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["pip"], 30)

    with pytest.raises(PipProviderError, match="Unable to run"):
        PipProvider(environment, runner=runner).list_installed()