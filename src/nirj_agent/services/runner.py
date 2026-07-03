from threading import Event

from nirj_agent.storage.paths import AgentPaths


def run_agent(
    paths: AgentPaths,
    stop_event: Event,
) -> None:
    print("Agent is running", flush=True)
    stop_event.wait()
