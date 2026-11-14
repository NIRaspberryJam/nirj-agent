"""Make the managed Python environment available to the classroom user."""

import json
import os
from pathlib import Path
import re
import shlex
import stat

from nirj_agent.storage.files import write_bytes
from nirj_agent.storage.paths import AgentPaths


START = "# BEGIN NIRJ managed Python"
END = "# END NIRJ managed Python"
SETTING = "python.defaultInterpreterPath"
# Keep string literals intact when recognizing JSONC comments and punctuation.
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|\s+|[^\s"{}\[\],:]+|[{}\[\],:]')


def _settings(content: str, interpreter: str) -> str:
    tokens = [
        match for match in TOKENS.finditer(content)
        if not match[0].isspace() and not match[0].startswith(("//", "/*"))
    ]
    normalized = "".join(
        token[0] for index, token in enumerate(tokens)
        if not (token[0] == "," and index + 1 < len(tokens)
                and tokens[index + 1][0] in ("}", "]"))
    )
    data = json.loads(normalized)
    if not isinstance(data, dict):
        raise ValueError("VS Code settings must be a JSON object")
    depth = 0
    replacements = []
    for index, token in enumerate(tokens):
        value = token[0]
        if (depth == 1 and value.startswith('"')
                and json.loads(value) == SETTING
                and tokens[index + 1][0] == ":"):
            start = index + 2
            end = start
            nested = 0
            while end < len(tokens):
                item = tokens[end][0]
                if nested == 0 and item in (",", "}"):
                    break
                nested += (item in ("{", "[")) - (item in ("}", "]"))
                end += 1
            replacements.append((tokens[start].start(), tokens[end - 1].end()))
        depth += (value in ("{", "[")) - (value in ("}", "]"))
    encoded = json.dumps(interpreter)
    if replacements:
        for start, end in reversed(replacements):
            content = content[:start] + encoded + content[end:]
        return content
    position = tokens[0].end()
    entry = f'\n    "{SETTING}": {encoded}' + ("," if data else "") + "\n"
    return content[:position] + entry + content[position:]


def _shell(content: str, bin_dir: str) -> str:
    directory = shlex.quote(bin_dir)
    block = f'''{START}
if [ -x {directory}/python ] && [ -z "${{VIRTUAL_ENV:-}}" ]; then
    case "$PATH" in
        {directory}|{directory}:*) ;;
        *) export PATH={directory}:"$PATH" ;;
    esac
fi
{END}
'''
    if START in content or END in content:
        pattern = re.compile(r"(?m)^" + re.escape(START) + r"\n[\s\S]*?^" + re.escape(END) + r"\n?")
        if content.count(START) != 1 or content.count(END) != 1 or not pattern.search(content):
            raise ValueError("Malformed NIRJ managed Python block")
        return pattern.sub(lambda _: block, content)
    return content + ("\n" if content and not content.endswith("\n") else "") + "\n" + block


def _changes(paths: AgentPaths) -> list[tuple[Path, bytes]]:
    home = paths.desktop_dir.parent
    if not home.is_dir() or not (paths.python_environment / "bin/python").exists():
        return []
    shell_files = [home / name for name in (".profile", ".bashrc", ".xprofile")]
    # Bash ignores .profile when either of these already exists.
    shell_files.extend(home / name for name in (".bash_profile", ".bash_login") if (home / name).exists())
    settings = home / ".config/Code/User/settings.json"
    changes = []
    for path in [*shell_files, settings]:
        content = path.read_text() if path.exists() else ("{}\n" if path == settings else "")
        desired = (_settings(content, str(paths.python_environment / "bin/python"))
                   if path == settings else _shell(content, str(paths.python_environment / "bin")))
        if content != desired:
            changes.append((path, desired.encode()))
    return changes


def python_setup_needs_reconcile(paths: AgentPaths) -> bool:
    return bool(_changes(paths))


def reconcile_python_setup(paths: AgentPaths) -> None:
    changes = _changes(paths)
    if not changes:
        return
    owner = paths.desktop_dir.parent.stat()
    for path, content in changes:
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
        # Follow existing user symlinks instead of replacing them.
        target = path.resolve()
        write_bytes(target, content)
        target.chmod(stat.S_IMODE(previous.st_mode) if previous else 0o644)
        if os.geteuid() == 0:
            os.chown(target, previous.st_uid if previous else owner.st_uid,
                     previous.st_gid if previous else owner.st_gid)
