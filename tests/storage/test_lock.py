from pathlib import Path

import pytest

from nirj_agent.storage.lock import LockError, exclusive_lock


def test_exclusive_lock_creates_lock_file(tmp_path: Path) -> None:
    path = tmp_path / "run" / "apply.lock"

    with exclusive_lock(path):
        assert path.exists()


def test_exclusive_lock_rejects_second_holder(tmp_path: Path) -> None:
    path = tmp_path / "apply.lock"

    with exclusive_lock(path):
        with pytest.raises(LockError, match="already running"):
            with exclusive_lock(path):
                pass
