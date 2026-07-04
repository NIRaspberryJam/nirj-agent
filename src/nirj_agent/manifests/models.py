from dataclasses import dataclass


SUPPORTED_DESKTOP_SHORTCUTS = frozenset({"vscode"})


@dataclass(frozen=True)
class AptManifest:
    enforce: bool
    packages: tuple[str, ...]


@dataclass(frozen=True)
class DesktopManifest:
    shortcuts: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    schema: int
    apt: AptManifest
    desktop: DesktopManifest
    overlay_enabled: bool
    background_enabled: bool

@dataclass(frozen=True)
class ManifestDocument:
    manifest: Manifest
    sha256: str
    source_url: str
    content: bytes
