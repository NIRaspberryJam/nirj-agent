from threading import Event

from nirj_agent.services.apply import ApplyResult
from nirj_agent.services.reconciliation import PackagePlan
from nirj_agent.services.runner import run_agent
from nirj_agent.state import AgentState
from nirj_agent.storage.paths import AgentPaths


def test_run_agent_refreshes_applies_and_waits(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    stop_event = Event()
    stop_event.set()
    calls = []
    config = object()
    client = object()
    provider = object()
    result = ApplyResult(
        plan=PackagePlan(
            desired=("git",),
            install=("git",),
            remove=(),
            unchanged=(),
        ),
        state=AgentState(
            manifest_hash="abc123",
            last_apply="2026-07-01T00:00:00Z",
            packages=("git",),
            overlay_enabled=False,
            ready=False,
        ),
    )

    monkeypatch.setattr(
        "nirj_agent.services.runner.load_config",
        lambda path: calls.append(("load", path)) or config,
    )

    def refresh(**kwargs) -> None:
        calls.append(("refresh", kwargs))

    def apply(**kwargs) -> ApplyResult:
        calls.append(("apply", kwargs))
        return result

    monkeypatch.setattr("nirj_agent.services.runner.refresh_manifest", refresh)
    monkeypatch.setattr("nirj_agent.services.runner.apply_manifest", apply)

    actual = run_agent(
        paths=paths,
        stop_event=stop_event,
        manifest_client=client,
        package_provider=provider,
    )

    assert actual is result
    assert calls == [
        ("load", paths.config),
        (
            "refresh",
            {"config": config, "paths": paths, "client": client},
        ),
        ("apply", {"paths": paths, "package_provider": provider}),
    ]
    assert "Initial reconciliation complete" in capsys.readouterr().out
