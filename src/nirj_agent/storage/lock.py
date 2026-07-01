import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


class LockError(RuntimeError):
    pass


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    handle: TextIO | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        if handle is not None:
            handle.close()
        raise LockError(f"Another apply operation is already running") from exc
    except OSError as exc:
        if handle is not None:
            handle.close()
        raise LockError(f"Unable to acquire apply lock {path}: {exc}") from exc

    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
