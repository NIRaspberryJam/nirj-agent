"""Configure direct execution in the Raspberry Pi desktop's PCManFM."""

from pathlib import Path
import re

from nirj_agent.storage.paths import AgentPaths


SECTION = re.compile(r"^\s*\[([^]]+)\]\s*(?:[#;].*)?$")


def _direct_execution(
    content: str, section_name: str = "config", key: str = "quick_exec", value: str = "1",
) -> str:
    key_pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    setting = f"{key}={value}\n"
    lines = content.splitlines(keepends=True)
    in_config = False
    found_section = False
    found_key = False
    result = []
    for line in lines:
        section = SECTION.match(line.strip())
        if section:
            if in_config and not found_key:
                result.append(setting)
            in_config = section[1] == section_name
            if in_config:
                found_section = True
                found_key = False
        if in_config and key_pattern.match(line):
            # Keep only one effective value within each config section.
            if not found_key:
                result.append(setting)
            found_key = True
        else:
            result.append(line)
    if result and not result[-1].endswith("\n"):
        result[-1] += "\n"
    if in_config and not found_key:
        result.append(setting)
    if not found_section:
        result.append(f"[{section_name}]\n" + setting)
    return "".join(result)


def _changes(paths: AgentPaths) -> list[tuple[Path, bytes]]:
    home = paths.desktop_dir.parent
    if not home.is_dir():
        return []
    files = [(home / ".config/libfm/libfm.conf", "config", "quick_exec", "1")]
    desktop = home / ".config/pcmanfm"
    monitors = set(desktop.glob("*/desktop-items-*.conf"))
    # Seed the Pi 5 HDMI profiles even before PCManFM has written them.
    monitors.update(desktop / "default" / f"desktop-items-HDMI-A-{index}.conf" for index in (1, 2))
    files.extend((path, "*", "show_mounts", "0") for path in sorted(monitors))
    changes = []
    for path, section, key, value in files:
        content = path.read_text() if path.exists() else ""
        desired = _direct_execution(content, section, key, value)
        if desired != content:
            changes.append((path, desired.encode()))
    return changes


def desktop_preferences_need_reconcile(paths: AgentPaths) -> bool:
    return bool(_changes(paths))


def reconcile_desktop_preferences(paths: AgentPaths) -> None:
    from .user_files import write_user_file
    for path, content in _changes(paths):
        write_user_file(path, content, paths.desktop_dir.parent)
