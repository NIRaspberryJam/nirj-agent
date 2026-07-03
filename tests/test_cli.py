from importlib import import_module
from uuid import UUID

from nirj_agent.config import (
    AgentConfig,
    DeviceConfig,
    DeviceType,
    ManifestSource,
)
from nirj_agent.state import AgentState

cli = import_module("nirj_agent.cli.main")


def test_status_returns_zero_when_ready(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_state",
        lambda _path: AgentState("abc123", None, ("thonny",), True, True),
    )
    result = cli.main(["status"])
    assert result == 0
    assert '"ready": true' in capsys.readouterr().out


def test_status_returns_one_when_not_ready(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_state",
        lambda _path: AgentState(None, None, (), False, False),
    )
    result = cli.main(["status"])
    assert result == 1
    assert '"ready": false' in capsys.readouterr().out


def test_get_config_calls_loader(monkeypatch, capsys) -> None:
    config = AgentConfig(
        device=DeviceConfig(
            id=UUID("fc41017d-0937-49f2-a49d-a64164d9cc2e"),
            asset_id="PI5-001",
            type=DeviceType.PI5,
        ),
        manifest=ManifestSource(
            type="github",
            repo="NIRaspberryJam/nirj-infra",
            path="manifests/pi5.manifest.yaml",
        ),
        overlay_enabled=True,
        background_enabled=True,
    )
    monkeypatch.setattr(cli, "load_config", lambda _path: config)
    result = cli.main(["get-config"])
    output = capsys.readouterr().out
    assert result == 0
    assert '"asset_id": "PI5-001"' in output
    assert str(config.device.id) in output


def test_status_uses_sandbox_state_path(tmp_path, monkeypatch, capsys) -> None:
    loaded_paths = []

    def load_test_state(path):
        loaded_paths.append(path)
        return AgentState(None, None, (), False, False)

    monkeypatch.setattr(cli, "load_state", load_test_state)

    result = cli.main(["--root", str(tmp_path), "status"])

    assert result == 1
    assert loaded_paths == [tmp_path / "data/nirj/state/state.yaml"]
    capsys.readouterr()


def test_up_rejects_sandbox_root(tmp_path, capsys) -> None:
    result = cli.main(["--root", str(tmp_path), "up"])

    assert result == 1
    assert "does not support --root" in capsys.readouterr().err


def test_up_requires_root(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)

    result = cli.main(["up"])

    assert result == 1
    assert "must run as root" in capsys.readouterr().err


def test_up_runs_agent_as_root(monkeypatch) -> None:
    received = {}
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)

    def run_test_agent(**kwargs) -> None:
        received.update(kwargs)

    monkeypatch.setattr(cli, "run_agent", run_test_agent)

    result = cli.main(["up"])

    assert result == 0
    assert received["paths"] == cli.AgentPaths.system()
    assert isinstance(received["stop_event"], cli.Event)
    assert set(received) == {"paths", "stop_event"}
