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


def test_update_install_and_remove_use_safe_commands() -> None:
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    provider = AptProvider(runner=runner, command_timeout=600)
    provider.update()
    provider.install(("git", "thonny"))
    provider.remove(("obsolete",))

    assert [call[0] for call in calls] == [
        ["apt-get", "update"],
        [
            "apt-get",
            "install",
            "--yes",
            "--no-remove",
            "--",
            "git",
            "thonny",
        ],
        ["apt-get", "remove", "--yes", "--", "obsolete"],
    ]
    assert all(call[1]["timeout"] == 600 for call in calls)


def test_empty_install_and_remove_execute_nothing() -> None:
    calls = []
    provider = AptProvider(runner=lambda *args, **kwargs: calls.append(args))

    provider.install(())
    provider.remove(())

    assert calls == []


def test_apt_operation_failure_is_reported() -> None:
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=100, stdout="", stderr="apt failed")

    with pytest.raises(AptProviderError, match="package installation failed"):
        AptProvider(runner=runner).install(("thonny",))


def test_apt_operation_timeout_is_wrapped() -> None:
    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("apt-get", 1800)

    with pytest.raises(AptProviderError, match="Unable to run package removal"):
        AptProvider(runner=runner).remove(("obsolete",))
