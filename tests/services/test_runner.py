from threading import Event

from nirj_agent.services.runner import run_agent
from nirj_agent.storage.paths import AgentPaths


def test_run_agent_is_idle_and_waits(tmp_path, capsys) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    stop_event = Event()
    stop_event.set()

    assert run_agent(paths=paths, stop_event=stop_event) is None
    assert "Agent is running" in capsys.readouterr().out
