import hashlib
from dataclasses import dataclass, replace

from nirj_agent.config import load_config
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.manifests.parser import parse_manifest
from nirj_agent.providers import AptProvider
from nirj_agent.services.apply import ApplyResult, apply_manifest
from nirj_agent.services.manifest import refresh_manifest
from nirj_agent.state import load_state, save_state
from nirj_agent.storage.files import read_bytes, write_bytes
from nirj_agent.storage.paths import AgentPaths


@dataclass(frozen=True)
class UpdateCheck:
    update_available: bool
    current_hash: str | None
    target_hash: str
    source: str


def check_for_update(
    paths: AgentPaths,
    client: GitHubManifestClient,
    persist_target: bool = False,
) -> UpdateCheck:
    config = load_config(paths.config)
    if persist_target:
        document = refresh_manifest(config, paths, client)
        target_hash = document.sha256
        source = document.source_url
    else:
        source, content = client.fetch(config.manifest)
        parse_manifest(content, source)
        target_hash = hashlib.sha256(content).hexdigest()

    current_hash = None
    if paths.current_manifest.exists():
        current_hash = hashlib.sha256(read_bytes(paths.current_manifest)).hexdigest()

    return UpdateCheck(
        update_available=current_hash != target_hash,
        current_hash=current_hash,
        target_hash=target_hash,
        source=source,
    )


def apply_target(
    paths: AgentPaths,
    package_provider: AptProvider,
) -> ApplyResult:
    result = apply_manifest(paths, package_provider)
    content = read_bytes(paths.target_manifest)
    write_bytes(paths.current_manifest, content)
    ready_state = replace(result.state, ready=True)
    save_state(ready_state, paths.state)
    return ApplyResult(plan=result.plan, state=ready_state)
