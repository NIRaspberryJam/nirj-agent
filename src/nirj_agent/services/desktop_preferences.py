"""Configure direct execution in the Raspberry Pi desktop's PCManFM."""

import os
from pathlib import Path
import re
import stat

from nirj_agent.storage.files import write_bytes
from nirj_agent.storage.paths import AgentPaths


SECTION = re.compile(r"^\s*\[([^]]+)\]\s*(?:[#;].*)?$")
QUICK_EXEC = re.compile(r"^\s*quick_exec\s*=")


def _direct_execution(content: str) -> str:
    lines = content.splitlines(keepends=True)
    in_config = False
    found_section = False
    found_key = False
    result = []
    for line in lines:
        section = SECTION.match(line.strip())
        if section:
            if in_config and not found_key:
                result.append("quick_exec=1\n")
            in_config = section[1] == "config"
            if in_config:
                found_section = True
                found_key = False
        if in_config and QUICK_EXEC.match(line):
            # Keep only one effective value within each config section.
            if not found_key:
                result.append("quick_exec=1\n")
            found_key = True
        else:
            result.append(line)
    if result and not result[-1].endswith("\n"):
        result[-1] += "\n"
    if in_config and not found_key:
        result.append("quick_exec=1\n")
    if not found_section:
        result.append("[config]\nquick_exec=1\n")
    return "".join(result)


def _change(paths: AgentPaths) -> tuple[Path, bytes] | None:
    home = paths.desktop_dir.parent
    if not home.is_dir():
        return None
    path = home / ".config/libfm/libfm.conf"
    content = path.read_text() if path.exists() else ""
    desired = _direct_execution(content)
    return (path, desired.encode()) if desired != content else None


def desktop_preferences_need_reconcile(paths: AgentPaths) -> bool:
    return _change(paths) is not None


def reconcile_desktop_preferences(paths: AgentPaths) -> None:
    change = _change(paths)
    if change is None:
        return
    path, content = change
    owner = paths.desktop_dir.parent.stat()
    previous = path.stat() if path.exists() else None
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        if os.geteuid() == 0:
            os.chown(directory, owner.st_uid, owner.st_gid)
    # Preserve existing user symlinks, file permissions and ownership.
    target = path.resolve()
    write_bytes(target, content)
    target.chmod(stat.S_IMODE(previous.st_mode) if previous else 0o644)
    if os.geteuid() == 0:
        os.chown(target, previous.st_uid if previous else owner.st_uid,
                 previous.st_gid if previous else owner.st_gid)
