from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from nirj_agent.manifests.github import ManifestDownloadError


cli = import_module("nirj_agent.cli.main")


def test_manifest_refresh_prints_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda _path: object())
    monkeypatch.setattr(cli, "GitHubManifestClient", lambda: object())
    monkeypatch.setattr(
        cli,
        "refresh_manifest",
        lambda **_kwargs: SimpleNamespace(
            manifest=SimpleNamespace(
                schema=1,
                apt=SimpleNamespace(packages=("git", "thonny")),
            ),
            sha256="abc123",
            source_url="https://example.test/manifest.yaml",
        ),
    )

    result = cli.main(["--root", str(tmp_path), "manifest", "refresh"])

    output = capsys.readouterr()
    assert result == 0
    assert '"sha256": "abc123"' in output.out
    assert '"packages": 2' in output.out
    assert str(tmp_path / "var/lib/nirj-agent/manifests/current.yaml") in output.out
    assert output.err == ""


def test_manifest_refresh_reports_expected_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(cli, "load_config", lambda _path: object())
    monkeypatch.setattr(cli, "GitHubManifestClient", lambda: object())

    def fail_refresh(**_kwargs):
        raise ManifestDownloadError("offline")

    monkeypatch.setattr(cli, "refresh_manifest", fail_refresh)

    result = cli.main(["--root", str(tmp_path), "manifest", "refresh"])

    output = capsys.readouterr()
    assert result == 1
    assert output.out == ""
    assert "Manifest refresh failed: offline" in output.err
