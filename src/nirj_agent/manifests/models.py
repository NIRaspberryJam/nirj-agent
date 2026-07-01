from dataclasses import dataclass


@dataclass(frozen=True)
class AptManifest:
    enforce: bool
    packages: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    schema: int
    apt: AptManifest
    overlay_enabled: bool
    background_enabled: bool

@dataclass(frozen=True)
class ManifestDocument:
    manifest: Manifest
    sha256: str
    source_url: str
    content: bytes
