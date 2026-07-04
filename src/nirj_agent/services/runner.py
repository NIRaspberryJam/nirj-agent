from threading import Event

from nirj_agent.config import DeviceType, load_config
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.storage.paths import AgentPaths

from .windows import reconcile_windows


def run_agent(
    paths: AgentPaths,
    stop_event: Event,
    client: GitHubManifestClient | None = None,
) -> None:
    config = load_config(paths.config)
    if config.device.type is DeviceType.LAPTOP_WINDOWS:
        reconcile_windows(
            paths=paths,
            client=client or GitHubManifestClient(),
        )
    print("Agent is running", flush=True)
    stop_event.wait()
