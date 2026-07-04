from threading import Event

from nirj_agent.config import DeviceType, create_config
from nirj_agent.services.runner import run_agent
from nirj_agent.state import load_state
from nirj_agent.storage.paths import AgentPaths


WINDOWS_MANIFEST = b"""schema: 1
apt:
  enforce: false
  packages: []
overlay:
  enabled: false
background:
  enabled: false
"""


class Client:
    def fetch(self, _source):
        return "https://example.test/lpt-win.manifest.yaml", WINDOWS_MANIFEST


def test_run_agent_is_idle_and_waits(tmp_path, capsys) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)
    stop_event = Event()
    stop_event.set()

    assert run_agent(paths=paths, stop_event=stop_event) is None
    assert "Agent is running" in capsys.readouterr().out


def test_run_agent_reconciles_windows_before_waiting(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("WIN-001", DeviceType.LAPTOP_WINDOWS, paths.config)
    stop_event = Event()
    stop_event.set()

    run_agent(paths=paths, stop_event=stop_event, client=Client())

    assert load_state(paths.state).ready is True
    assert paths.current_manifest.read_bytes() == WINDOWS_MANIFEST
