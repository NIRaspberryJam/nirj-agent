from pathlib import Path

import pytest

from nirj_agent.manifests import ManifestError, load_manifest, parse_manifest


VALID_MANIFEST = b"""\
schema: 1
apt:
  enforce: true
  packages:
    - thonny
    - git
overlay:
  enabled: false
background:
  enabled: true
"""


def test_parse_manifest_from_bytes() -> None:
    manifest = parse_manifest(VALID_MANIFEST, "test manifest")

    assert manifest.schema == 1
    assert manifest.apt.enforce is True
    assert manifest.apt.packages == ("thonny", "git")
    assert manifest.overlay_enabled is False
    assert manifest.background_enabled is True


def test_load_manifest_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_bytes(VALID_MANIFEST)

    assert load_manifest(path) == parse_manifest(VALID_MANIFEST)


def test_parse_manifest_rejects_invalid_utf8() -> None:
    with pytest.raises(ManifestError, match="not valid UTF-8"):
        parse_manifest(b"\xff", "invalid manifest")


def test_parse_manifest_rejects_invalid_yaml() -> None:
    with pytest.raises(ManifestError, match="invalid YAML"):
        parse_manifest(b"schema: [", "invalid manifest")


@pytest.mark.parametrize("content", [b"", b"- schema\n- 1\n"])
def test_parse_manifest_requires_top_level_mapping(content: bytes) -> None:
    with pytest.raises(ManifestError, match="must be a YAML mapping"):
        parse_manifest(content)


@pytest.mark.parametrize("schema", [b"true", b"'1'", b"null"])
def test_parse_manifest_requires_integer_schema(schema: bytes) -> None:
    with pytest.raises(ManifestError, match="schema as an integer"):
        parse_manifest(b"schema: " + schema + b"\n")


@pytest.mark.parametrize("section", [b"apt", b"overlay", b"background"])
def test_parse_manifest_requires_section_mappings(section: bytes) -> None:
    content = b"schema: 1\n" + section + b": []\n"

    with pytest.raises(ManifestError, match="must be a YAML mapping"):
        parse_manifest(content)


@pytest.mark.parametrize(
    "content",
    [
        b"schema: 1\napt:\n  enforce: 'false'\n",
        b"schema: 1\noverlay:\n  enabled: 0\n",
        b"schema: 1\nbackground:\n  enabled: 'yes'\n",
    ],
)
def test_parse_manifest_requires_real_booleans(content: bytes) -> None:
    with pytest.raises(ManifestError, match="must be true or false"):
        parse_manifest(content)


def test_parse_manifest_rejects_blank_package_name() -> None:
    content = b"schema: 1\napt:\n  packages: ['   ']\n"

    with pytest.raises(ManifestError, match="apt.packages"):
        parse_manifest(content)


@pytest.mark.parametrize("package", ["--option", "UPPERCASE", "bad name"])
def test_parse_manifest_rejects_unsafe_package_name(package: str) -> None:
    content = f"schema: 1\napt:\n  packages: ['{package}']\n".encode()

    with pytest.raises(ManifestError, match="apt.packages"):
        parse_manifest(content)
