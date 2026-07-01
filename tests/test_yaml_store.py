from pathlib import Path

import pytest

from nirj_agent.storage.yaml import YamlStoreError, read_yaml, write_yaml


def test_write_and_read_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    write_yaml(path, {"device": {"asset_id": "PI5-001"}})
    assert read_yaml(path) == {"device": {"asset_id": "PI5-001"}}


def test_write_creates_missing_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.yaml"
    write_yaml(path, {"ready": True})
    assert read_yaml(path) == {"ready": True}


def test_write_allows_existing_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "state.yaml"
    write_yaml(path, {"ready": True})
    write_yaml(path, {"ready": False})
    assert read_yaml(path) == {"ready": False}


def test_read_empty_yaml_returns_empty_mapping(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert read_yaml(path) == {}


def test_read_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- thonny\n- scratch\n", encoding="utf-8")
    with pytest.raises(YamlStoreError, match="must contain a YAML mapping"):
        read_yaml(path)


def test_read_wraps_missing_file_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"
    with pytest.raises(YamlStoreError, match="Unable to read"):
        read_yaml(path)


def test_read_wraps_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("device: [\n", encoding="utf-8")
    with pytest.raises(YamlStoreError, match="Unable to read"):
        read_yaml(path)
