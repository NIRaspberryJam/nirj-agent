from pathlib import Path

import pytest

from nirj_agent.manifests import ManifestError, load_manifest


def test_load_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        """
schema: 1
apt:
  enforce: true
  packages:
    - thonny
    - scratch
overlay:
  enabled: true
background:
  enabled: false
""",
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    assert manifest.schema == 1
    assert manifest.apt.enforce is True
    assert manifest.apt.packages == ("thonny", "scratch")
    assert manifest.overlay_enabled is True
    assert manifest.background_enabled is False


def test_manifest_removes_duplicate_packages(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        """
schema: 1
apt:
  packages:
    - thonny
    - scratch
    - thonny
""",
        encoding="utf-8",
    )
    assert load_manifest(path).apt.packages == ("thonny", "scratch")


def test_manifest_defaults_optional_values(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text("schema: 1\n", encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.apt.enforce is False
    assert manifest.apt.packages == ()
    assert manifest.overlay_enabled is False
    assert manifest.background_enabled is False


def test_manifest_rejects_unknown_schema(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text("schema: 2\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="Unsupported manifest schema"):
        load_manifest(path)


@pytest.mark.parametrize(
    "packages",
    ["thonny", "[thonny, '']", "[thonny, 42]"],
)
def test_manifest_rejects_invalid_packages(
    tmp_path: Path,
    packages: str,
) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"schema: 1\napt:\n  packages: {packages}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="apt.packages"):
        load_manifest(path)
