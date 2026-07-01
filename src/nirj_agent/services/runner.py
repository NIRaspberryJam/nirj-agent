from threading import Event

from nirj_agent.config import load_config
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.providers import AptProvider
from nirj_agent.services.apply import ApplyResult, apply_manifest
from nirj_agent.services.manifest import refresh_manifest
from nirj_agent.storage.paths import AgentPaths


def run_agent(
    paths: AgentPaths,
    stop_event: Event,
    manifest_client: GitHubManifestClient,
    package_provider: AptProvider,
) -> ApplyResult:
    config = load_config(paths.config)
    refresh_manifest(
        config=config,
        paths=paths,
        client=manifest_client,
    )
    result = apply_manifest(
        paths=paths,
        package_provider=package_provider,
    )

    print("Initial reconciliation complete; agent is running", flush=True)
    stop_event.wait()

    return result
