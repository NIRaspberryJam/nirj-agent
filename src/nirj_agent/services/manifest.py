import hashlib

from nirj_agent.config.models import AgentConfig
from nirj_agent.manifests.github import GitHubManifestClient
from nirj_agent.manifests.models import ManifestDocument
from nirj_agent.manifests.parser import parse_manifest
from nirj_agent.storage.files import write_bytes
from nirj_agent.storage.paths import AgentPaths


def refresh_manifest(
    config: AgentConfig,
    paths: AgentPaths,
    client: GitHubManifestClient,
) -> ManifestDocument:
    source_url, content = client.fetch(config.manifest)

    # Validate before replacing the working cache.
    manifest = parse_manifest(content, source_url)
    digest = hashlib.sha256(content).hexdigest()

    write_bytes(paths.manifest_cache, content)

    return ManifestDocument(
        manifest=manifest,
        sha256=digest,
        source_url=source_url,
        content=content,
    )