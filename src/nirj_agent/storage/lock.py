import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class LockError(RuntimeError):
    pass


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    handle: BinaryIO | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        _lock(handle)
    except OSError as exc:
        if handle is not None:
            handle.close()
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise LockError(
                "Another apply operation is already running"
            ) from exc
        raise LockError(f"Unable to acquire apply lock {path}: {exc}") from exc

    try:
        yield
    finally:
        _unlock(handle)
        handle.close()


def _lock(handle: BinaryIO) -> None:
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
