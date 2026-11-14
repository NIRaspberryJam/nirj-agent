import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nirj_agent.config import DeviceType, create_config
from nirj_agent.providers import AptProviderError
from nirj_agent.services.apply import ApplyError, PartialApplyError, apply_manifest
from nirj_agent.state import AgentState, load_state, save_state
from nirj_agent.storage.paths import AgentPaths


MANIFEST = b"""\
schema: 1
apt:
  enforce: true
  packages: [git, thonny]
"""


class FakeApplyProvider:
    def __init__(
        self,
        installed: set[str],
        fail_operation: str | None = None,
    ) -> None:
        self.installed = installed
        self.fail_operation = fail_operation
        self.events: list[object] = []

    def list_installed(self) -> set[str]:
        self.events.append("list")
        return self.installed

    def update(self) -> None:
        self.events.append("update")
        self._fail_if_requested("update")

    def install(self, packages: tuple[str, ...]) -> None:
        self.events.append(("install", packages))
        self._fail_if_requested("install")

    def remove(self, packages: tuple[str, ...]) -> None:
        self.events.append(("remove", packages))
        self._fail_if_requested("remove")

    def _fail_if_requested(self, operation: str) -> None:
        if self.fail_operation == operation:
            raise AptProviderError(f"{operation} failed")


class FakePythonProvider:
    def __init__(self, installed: dict[str, str] | None = None) -> None:
        self.installed = installed or {}
        self.events: list[object] = []

    def list_installed(self) -> dict[str, str]:
        self.events.append("list")
        return self.installed

    def install(self, requirements: tuple[str, ...]) -> None:
        self.events.append(("install", requirements))

    def remove(self, packages: tuple[str, ...]) -> None:
        self.events.append(("remove", packages))


def prepare(
    tmp_path: Path,
    device_type: DeviceType = DeviceType.PI5,
) -> AgentPaths:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("DEVICE-001", device_type, paths.config)
    paths.manifest_cache.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_cache.write_bytes(MANIFEST)
    return paths


def test_apply_runs_operations_in_order_and_persists_state(
    tmp_path: Path,
) -> None:
    paths = prepare(tmp_path)
    save_state(
        AgentState(
            manifest_hash="old",
            last_apply=None,
            packages=("git", "obsolete"),
            overlay_enabled=False,
            ready=False,
        ),
        paths.state,
    )
    provider = FakeApplyProvider({"git"})
    python_provider = FakePythonProvider()
    applied_at = datetime(2026, 7, 1, 12, 30, tzinfo=timezone.utc)

    result = apply_manifest(
        paths,
        provider,
        python_provider,
        clock=lambda: applied_at,
    )

    assert provider.events == [
        "list",
        "update",
        ("install", ("thonny",)),
        ("remove", ("obsolete",)),
    ]
    assert python_provider.events == ["list"]
    assert result.state.manifest_hash == hashlib.sha256(MANIFEST).hexdigest()
    assert result.state.last_apply == "2026-07-01T12:30:00Z"
    assert result.state.packages == ("git", "thonny")
    assert result.state.overlay_enabled is False
    assert result.state.ready is False
    assert load_state(paths.state) == result.state


def test_apply_skips_update_when_no_install_is_needed(tmp_path: Path) -> None:
    paths = prepare(tmp_path)
    provider = FakeApplyProvider({"git", "thonny"})
    python_provider = FakePythonProvider()

    apply_manifest(paths, provider, python_provider)

    assert provider.events == ["list"]
    assert python_provider.events == ["list"]


def test_apply_reconciles_vscode_shortcut_after_install(tmp_path: Path) -> None:
    paths = prepare(tmp_path)
    content = MANIFEST.replace(
        b"packages: [git, thonny]",
        b"packages: [code, git, thonny]",
    ) + b"desktop:\n  shortcuts: [vscode]\n"
    paths.manifest_cache.write_bytes(content)
    provider = FakeApplyProvider({"git"})
    python_provider = FakePythonProvider()

    apply_manifest(paths, provider, python_provider)

    shortcut = paths.desktop_dir / "visual-studio-code.desktop"
    assert shortcut.exists()
    assert provider.events[:3] == [
        "list",
        "update",
        ("install", ("code", "thonny")),
    ]


@pytest.mark.parametrize("failure", ["update", "install", "remove"])
def test_apply_failure_preserves_manifest_and_records_error(
    tmp_path: Path,
    failure: str,
) -> None:
    paths = prepare(tmp_path)
    previous = AgentState(
        manifest_hash="old",
        last_apply="2026-06-30T00:00:00Z",
        packages=("git", "obsolete"),
        overlay_enabled=False,
        ready=False,
    )
    save_state(previous, paths.state)
    installed = {"git"} if failure != "remove" else {"git", "thonny"}
    provider = FakeApplyProvider(installed, fail_operation=failure)
    python_provider = FakePythonProvider()

    with pytest.raises(PartialApplyError, match=failure):
        apply_manifest(paths, provider, python_provider)

    state = load_state(paths.state)
    assert state.manifest_hash == previous.manifest_hash
    assert state.last_apply == previous.last_apply
    assert state.ready is False
    assert state.errors == (f"{failure} failed",)


def test_apply_rejects_windows_before_querying_packages(tmp_path: Path) -> None:
    paths = prepare(tmp_path, DeviceType.LAPTOP_WINDOWS)
    provider = FakeApplyProvider(set())
    python_provider = FakePythonProvider()

    with pytest.raises(ApplyError, match="not supported for Windows"):
        apply_manifest(paths, provider, python_provider)

    assert provider.events == []
    assert python_provider.events == []
    assert not paths.state.exists()


def test_apply_reconciles_python_packages_and_persists_state(
    tmp_path: Path,
) -> None:
    paths = prepare(tmp_path)
    paths.manifest_cache.write_bytes(
        MANIFEST
        + b"python:\n"
        + b"  packages:\n"
        + b"    jamkit: '0.2.0'\n"
        + b"    requests: '2.32.5'\n"
    )
    save_state(
        AgentState(
            manifest_hash="old",
            last_apply=None,
            packages=("git", "thonny"),
            overlay_enabled=False,
            ready=False,
            python_packages=(("jamkit", "0.1.0"), ("obsolete", "1.0")),
        ),
        paths.state,
    )
    provider = FakeApplyProvider({"git", "thonny"})
    python_provider = FakePythonProvider(
        {"jamkit": "0.1.0", "requests": "2.32.5"}
    )

    result = apply_manifest(paths, provider, python_provider)

    assert python_provider.events == [
        "list",
        ("install", ("jamkit==0.2.0", "requests==2.32.5")),
        ("remove", ("obsolete",)),
    ]
    assert result.state.python_packages == (
        ("jamkit", "0.2.0"),
        ("requests", "2.32.5"),
    )
    assert load_state(paths.state) == result.state


def test_partial_apt_batch_tracks_only_observed_packages(tmp_path):
    paths = prepare(tmp_path)

    class PartialApt(FakeApplyProvider):
        def install(self, packages):
            self.installed.add("git")
            raise AptProviderError("thonny unavailable")

    with pytest.raises(PartialApplyError):
        apply_manifest(paths, PartialApt(set()), FakePythonProvider())

    assert load_state(paths.state).packages == ("git",)


def test_python_failure_preserves_failed_removal_and_allows_shortcuts(tmp_path):
    from nirj_agent.providers import PipProviderError

    paths = prepare(tmp_path)
    paths.manifest_cache.write_bytes(
        b"schema: 1\napt:\n  packages: [code]\n"
        b"python:\n  packages:\n    pyfiglet: '1.0.2'\n"
        b"desktop:\n  shortcuts: [vscode]\n"
    )
    save_state(AgentState("old", None, (), False, True,
                          (("obsolete", "1.0"),)), paths.state)

    class FailedPython(FakePythonProvider):
        def install(self, requirements):
            # Simulate a partially completed pip operation.
            self.installed["pyfiglet"] = "1.0.2"
            raise PipProviderError("installation failed")

        def remove(self, packages):
            raise PipProviderError("removal failed")

    with pytest.raises(PartialApplyError, match="removal failed"):
        apply_manifest(paths, FakeApplyProvider({"code"}),
                       FailedPython({"obsolete": "1.0"}))

    state = load_state(paths.state)
    assert not state.ready
    assert state.python_packages == (("obsolete", "1.0"), ("pyfiglet", "1.0.2"))
    assert (paths.desktop_dir / "visual-studio-code.desktop").exists()
