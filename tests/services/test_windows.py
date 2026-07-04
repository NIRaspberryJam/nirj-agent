from datetime import datetime, timezone

import pytest

from nirj_agent.config import DeviceType, create_config
from nirj_agent.services.windows import (
    WindowsReconcileError,
    reconcile_windows,
)
from nirj_agent.state import load_state
from nirj_agent.storage.paths import AgentPaths


VALID_MANIFEST = b"""schema: 1
apt:
  enforce: false
  packages: []
overlay:
  enabled: false
background:
  enabled: false
"""


class Client:
    def __init__(self, content: bytes = VALID_MANIFEST) -> None:
        self.content = content

    def fetch(self, _source):
        return "https://example.test/lpt-win.manifest.yaml", self.content


def test_reconcile_windows_promotes_manifest_and_marks_ready(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("WIN-001", DeviceType.LAPTOP_WINDOWS, paths.config)

    state = reconcile_windows(
        paths,
        Client(),
        clock=lambda: datetime(2026, 7, 4, 12, 30, tzinfo=timezone.utc),
    )

    assert state.ready is True
    assert state.last_apply == "2026-07-04T12:30:00Z"
    assert state.packages == ()
    assert state.overlay_enabled is False
    assert paths.target_manifest.read_bytes() == VALID_MANIFEST
    assert paths.current_manifest.read_bytes() == VALID_MANIFEST
    assert load_state(paths.state) == state


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("apt:\n  enforce: true\n  packages: []", "apt.enforce"),
        ("apt:\n  packages: [git]", "apt.packages"),
        (
            "apt:\n  packages: [code]\n"
            "desktop:\n  shortcuts: [vscode]",
            "desktop.shortcuts",
        ),
        ("overlay:\n  enabled: true", "overlay.enabled"),
        ("background:\n  enabled: true", "background.enabled"),
    ],
)
def test_reconcile_windows_rejects_linux_only_settings(
    tmp_path,
    section: str,
    expected: str,
) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("WIN-001", DeviceType.LAPTOP_WINDOWS, paths.config)
    content = f"schema: 1\n{section}\n".encode()

    with pytest.raises(WindowsReconcileError, match=expected):
        reconcile_windows(paths, Client(content))

    assert not paths.current_manifest.exists()
    assert not paths.state.exists()


def test_reconcile_windows_rejects_non_windows_device(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)

    with pytest.raises(WindowsReconcileError, match="lpt-win"):
        reconcile_windows(paths, Client())
