import subprocess
from types import SimpleNamespace

import pytest

from nirj_agent.providers import AptProvider, AptProviderError


def test_list_installed_parses_only_installed_packages() -> None:
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "git\tii \n"
                "python3\tii \n"
                "removed-package\trc \n"
                "malformed-line\n"
            ),
            stderr="",
        )

    packages = AptProvider(runner=runner).list_installed()

    assert packages == {"git", "python3"}
    command, kwargs = calls[0]
    assert command[0:2] == ["dpkg-query", "-W"]
    assert kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": 30,
    }


def test_list_installed_wraps_missing_command() -> None:
    def runner(*_args, **_kwargs):
        raise FileNotFoundError("dpkg-query")

    with pytest.raises(AptProviderError, match="Unable to query"):
        AptProvider(runner=runner).list_installed()


def test_list_installed_wraps_timeout() -> None:
    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("dpkg-query", 30)

    with pytest.raises(AptProviderError, match="Unable to query"):
        AptProvider(runner=runner).list_installed()


def test_list_installed_reports_command_failure() -> None:
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="database error")

    with pytest.raises(AptProviderError, match="database error"):
        AptProvider(runner=runner).list_installed()
