from pathlib import Path

import pytest

from nirj_agent.config import DeviceType, create_config
from nirj_agent.manifests import ManifestError
from nirj_agent.services.plan import PlanError, create_plan
from nirj_agent.state import AgentState, save_state
from nirj_agent.storage.paths import AgentPaths


class FakePackageProvider:
    def __init__(self, installed: set[str]) -> None:
        self.installed = installed
        self.called = False

    def list_installed(self) -> set[str]:
        self.called = True
        return self.installed


def write_manifest(path: Path, enforce: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "schema: 1\n"
            "apt:\n"
            f"  enforce: {str(enforce).lower()}\n"
            "  packages: [git, thonny]\n"
        ),
        encoding="utf-8",
    )


def test_create_plan_uses_config_manifest_state_and_provider(
    tmp_path: Path,
) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)
    write_manifest(paths.manifest_cache)
    save_state(
        AgentState(
            manifest_hash="old-hash",
            last_apply=None,
            packages=("git", "obsolete"),
            overlay_enabled=False,
            ready=False,
        ),
        paths.state,
    )
    provider = FakePackageProvider({"git"})

    plan = create_plan(paths, provider)

    assert provider.called is True
    assert plan.install == ("thonny",)
    assert plan.remove == ("obsolete",)
    assert plan.unchanged == ("git",)


def test_create_plan_does_not_write_files(tmp_path: Path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)
    write_manifest(paths.manifest_cache)
    config_before = paths.config.read_bytes()
    manifest_before = paths.manifest_cache.read_bytes()

    create_plan(paths, FakePackageProvider({"git", "thonny"}))

    assert paths.config.read_bytes() == config_before
    assert paths.manifest_cache.read_bytes() == manifest_before
    assert not paths.state.exists()


def test_create_plan_requires_cached_manifest(tmp_path: Path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-001", DeviceType.PI5, paths.config)

    with pytest.raises(ManifestError, match="Unable to read manifest"):
        create_plan(paths, FakePackageProvider(set()))


def test_create_plan_rejects_windows_before_querying_packages(
    tmp_path: Path,
) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("LPT-001", DeviceType.LAPTOP_WINDOWS, paths.config)
    provider = FakePackageProvider(set())

    with pytest.raises(PlanError, match="not supported for Windows"):
        create_plan(paths, provider)

    assert provider.called is False
