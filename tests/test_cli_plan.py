from importlib import import_module
from pathlib import Path

from nirj_agent.providers import AptProviderError
from nirj_agent.services.reconciliation import PackagePlan


cli = import_module("nirj_agent.cli.main")


def test_plan_prints_package_changes(tmp_path: Path, monkeypatch, capsys) -> None:
    provider = object()
    monkeypatch.setattr(cli, "AptProvider", lambda: provider)

    def create_test_plan(paths, package_provider):
        assert paths.manifest_cache == (
            tmp_path / "data/nirj/state/target-manifest.json"
        )
        assert package_provider is provider
        return PackagePlan(
            desired=("git", "thonny"),
            install=("thonny",),
            remove=("obsolete",),
            unchanged=("git",),
        )

    monkeypatch.setattr(cli, "create_plan", create_test_plan)

    result = cli.main(["--root", str(tmp_path), "plan"])

    output = capsys.readouterr()
    assert result == 0
    assert '"changes_required": true' in output.out
    assert '"install": [' in output.out
    assert '"thonny"' in output.out
    assert '"obsolete"' in output.out
    assert output.err == ""


def test_plan_reports_provider_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "AptProvider", lambda: object())

    def fail_plan(**_kwargs):
        raise AptProviderError("dpkg-query failed")

    monkeypatch.setattr(cli, "create_plan", fail_plan)

    result = cli.main(["--root", str(tmp_path), "plan"])

    output = capsys.readouterr()
    assert result == 1
    assert output.out == ""
    assert "Package planning failed: dpkg-query failed" in output.err
