from pathlib import Path

import pytest

from nirj_agent.storage.files import FileStoreError, write_bytes


def test_write_bytes_creates_parent_and_writes_content(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "manifest.yaml"

    write_bytes(path, b"schema: 1\n")

    assert path.read_bytes() == b"schema: 1\n"
    assert not path.with_suffix(".yaml.tmp").exists()


def test_write_bytes_replaces_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_bytes(b"old")

    write_bytes(path, b"new")

    assert path.read_bytes() == b"new"


def test_write_bytes_cleans_up_temporary_file_on_replace_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_bytes(b"old")

    def fail_replace(_self, _target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(FileStoreError, match="replace failed"):
        write_bytes(path, b"new")

    assert path.read_bytes() == b"old"
    assert not path.with_suffix(".yaml.tmp").exists()
