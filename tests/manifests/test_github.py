from urllib.error import URLError

import pytest

from nirj_agent.config import ManifestSource
from nirj_agent.manifests.github import (
    GitHubManifestClient,
    ManifestDownloadError,
)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.requested_size: int | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, size: int) -> bytes:
        self.requested_size = size
        return self.content[:size]


def source(**overrides) -> ManifestSource:
    values = {
        "type": "github",
        "repo": "NIRaspberryJam/nirj-infra",
        "path": "manifests/pi5.manifest.yaml",
        "ref": "main",
    }
    values.update(overrides)
    return ManifestSource(**values)


def test_build_url() -> None:
    assert GitHubManifestClient.build_url(source()) == (
        "https://raw.githubusercontent.com/"
        "NIRaspberryJam/nirj-infra/main/manifests/pi5.manifest.yaml"
    )


def test_build_url_encodes_ref_and_path() -> None:
    result = GitHubManifestClient.build_url(
        source(ref="feature/test", path="manifests/test file.yaml")
    )

    assert "/feature%2Ftest/" in result
    assert result.endswith("manifests/test%20file.yaml")


@pytest.mark.parametrize(
    "overrides",
    [
        {"repo": "missing-owner"},
        {"ref": ""},
        {"path": ""},
        {"path": "/absolute.yaml"},
        {"path": "manifests/../secret.yaml"},
    ],
)
def test_build_url_rejects_unsafe_source(overrides) -> None:
    with pytest.raises(ManifestDownloadError):
        GitHubManifestClient.build_url(source(**overrides))


def test_fetch_returns_url_and_content() -> None:
    response = FakeResponse(b"schema: 1\n")

    def opener(_url, timeout):
        assert timeout == 3
        return response

    client = GitHubManifestClient(
        timeout=3,
        maximum_size=100,
        opener=opener,
    )

    url, content = client.fetch(source())

    assert url.endswith("/main/manifests/pi5.manifest.yaml")
    assert content == b"schema: 1\n"
    assert response.requested_size == 101


def test_fetch_rejects_unsupported_source_type() -> None:
    client = GitHubManifestClient(opener=lambda *_args, **_kwargs: None)

    with pytest.raises(ManifestDownloadError, match="Unsupported"):
        client.fetch(source(type="local"))


def test_fetch_rejects_oversized_manifest() -> None:
    response = FakeResponse(b"123456")
    client = GitHubManifestClient(
        maximum_size=5,
        opener=lambda *_args, **_kwargs: response,
    )

    with pytest.raises(ManifestDownloadError, match="exceeds 5 bytes"):
        client.fetch(source())


@pytest.mark.parametrize(
    "error",
    [URLError("offline"), TimeoutError("timed out"), OSError("socket failed")],
)
def test_fetch_wraps_network_failures(error: OSError) -> None:
    def opener(*_args, **_kwargs):
        raise error

    client = GitHubManifestClient(opener=opener)

    with pytest.raises(ManifestDownloadError, match="Unable to download"):
        client.fetch(source())
