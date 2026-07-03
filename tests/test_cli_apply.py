from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from nirj_agent.providers import AptProviderError
from nirj_agent.services.reconciliation import PackagePlan
from nirj_agent.state import AgentState


cli = import_module("nirj_agent.cli.main")


def test_apply_rejects_sandbox_root(tmp_path: Path, capsys) -> None:
    result = cli.main(["--root", str(tmp_path), "apply"])

    output = capsys.readouterr()
    assert result == 1
    assert "does not support --root" in output.err


def test_apply_requires_root(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)

    result = cli.main(["apply"])

    output = capsys.readouterr()
    assert result == 1
    assert "must run as root" in output.err


def test_apply_prints_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    provider = object()
    monkeypatch.setattr(cli, "AptProvider", lambda: provider)
    plan = PackagePlan(
        desired=("git", "thonny"),
        install=("thonny",),
        remove=("obsolete",),
        unchanged=("git",),
    )
    state = AgentState(
        manifest_hash="abc123",
        last_apply="2026-07-01T12:30:00Z",
        packages=plan.desired,
        overlay_enabled=False,
        ready=False,
    )

    def apply_test_manifest(paths, package_provider):
        assert paths.config == Path("/data/nirj/config/config.yaml")
        assert package_provider is provider
        return SimpleNamespace(plan=plan, state=state)

    monkeypatch.setattr(cli, "apply_manifest", apply_test_manifest)

    result = cli.main(["apply"])

    output = capsys.readouterr()
    assert result == 0
    assert '"manifest_hash": "abc123"' in output.out
    assert '"thonny"' in output.out
    assert '"obsolete"' in output.out
    assert '"ready": false' in output.out
    assert output.err == ""


def test_apply_reports_provider_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "AptProvider", lambda: object())

    def fail_apply(**_kwargs):
        raise AptProviderError("apt failed")

    monkeypatch.setattr(cli, "apply_manifest", fail_apply)

    result = cli.main(["apply"])

    output = capsys.readouterr()
    assert result == 1
    assert "Package application failed: apt failed" in output.err
