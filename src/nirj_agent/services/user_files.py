"""Write managed user configuration without taking ownership from the user."""

import os
from pathlib import Path
import stat

from nirj_agent.storage.files import write_bytes


def user_directory(path: Path, home: Path) -> None:
    owner = home.stat()
    missing = []
    parent = path
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        if os.geteuid() == 0:
            os.chown(directory, owner.st_uid, owner.st_gid)


def write_user_file(path: Path, content: bytes, home: Path) -> None:
    previous = path.stat() if path.exists() else None
    owner = home.stat()
    user_directory(path.parent, home)
    target = path.resolve()
    write_bytes(target, content)
    target.chmod(stat.S_IMODE(previous.st_mode) if previous else 0o644)
    if os.geteuid() == 0:
        os.chown(target, previous.st_uid if previous else owner.st_uid,
                 previous.st_gid if previous else owner.st_gid)
