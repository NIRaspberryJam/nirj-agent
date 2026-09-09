from importlib import import_module

import pytest

from nirj_agent.services.boot import BootPrepResult


@pytest.mark.parametrize("arguments, expected", [(["boot-prep"], 0), (["update", "apply"], 1)])
def test_partial_update_allows_startup_but_reports_explicit_failure(
    monkeypatch, capsys, arguments, expected,
):
    cli = import_module("nirj_agent.cli.main")
    monkeypatch.setattr(cli, "_require_root", lambda *args: True)
    monkeypatch.setattr(cli, "boot_prep", lambda **kwargs: BootPrepResult("update_failed", False))

    assert cli.main(arguments) == expected
    assert '"action": "update_failed"' in capsys.readouterr().out
