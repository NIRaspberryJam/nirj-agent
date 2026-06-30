from pathlib import PurePosixPath
import re

from urllib.request import urlopen
from urllib.parse import quote

from nirj_agent.config.models import ManifestSource


REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)

class ManifestDownloadError(RuntimeError):
    pass

class GitHubManifestClient:
    def __init__(
        self,
        timeout: float = 10,
        maximum_size: int = 1024 * 1024,
        opener=urlopen,
    ) -> None:
        self.timeout = timeout
        self.maximum_size = maximum_size
        self.opener = opener

    def fetch(self, source: ManifestSource) -> tuple[str, bytes]:
        if source.type != "github":
            raise ManifestDownloadError(f"Unsupported manifest source type: {source.type}")
        
        url = self.build_url(source)

        try:
            with self.opener(url, timeout=self.timeout) as response:
                content = response.read(self.maximum_size + 1)
        except OSError as exc:
            raise ManifestDownloadError(
                f"Unable to download manifest from {url}: {exc}"
            ) from exc
        
        if len(content) > self.maximum_size:
            raise ManifestDownloadError(
                f"Manifest exceeds {self.maximum_size} bytes"
            )
        
        return url, content
    
    @staticmethod
    def build_url(source: ManifestSource) -> str:
        if not REPOSITORY_PATTERN.fullmatch(source.repo):
            raise ManifestDownloadError(
                f"Invalid GitHub repository: {source.repo}"
            )

        if not source.ref:
            raise ManifestDownloadError("Manifest ref cannot be empty")

        manifest_path = PurePosixPath(source.path)

        if (
            not source.path.strip()
            or manifest_path.is_absolute()
            or ".." in manifest_path.parts
        ):
            raise ManifestDownloadError(
                f"Invalid manifest path: {source.path}"
            )

        encoded_ref = quote(source.ref, safe="")
        encoded_path = quote(source.path, safe="/")

        return (
            "https://raw.githubusercontent.com/"
            f"{source.repo}/{encoded_ref}/{encoded_path}"
    )
