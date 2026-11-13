import pytest

from nirj_agent.services.desktop_preferences import (
    desktop_preferences_need_reconcile,
    reconcile_desktop_preferences,
)
from nirj_agent.services.desktop_setup import desktop_setup_needs_reconcile
from nirj_agent.storage.paths import AgentPaths


@pytest.mark.parametrize("existing", [
    "",
    "# Keep this comment\n[config]\nquick_exec=0\nterminal=lxterminal\n[ui]\nquick_exec=0\n",
    "[config]\nterminal=lxterminal\n[ui]\nbig_icon_size=48\n",
    "[ui]\nbig_icon_size=48",
])
def test_direct_execution_preserves_preferences_and_is_idempotent(tmp_path, existing):
    paths = AgentPaths.sandbox(tmp_path)
    path = paths.desktop_dir.parent / ".config/libfm/libfm.conf"
    path.parent.mkdir(parents=True)
    path.write_text(existing)
    path.chmod(0o600)
    assert desktop_preferences_need_reconcile(paths)
    reconcile_desktop_preferences(paths)
    content = path.read_text()
    assert "quick_exec=1\n" in content
    for line in existing.splitlines():
        if line != "quick_exec=0":
            assert line in content
    if "[ui]\nquick_exec=0" in existing:
        assert "[ui]\nquick_exec=0" in content
    assert path.stat().st_mode & 0o777 == 0o600
    assert not desktop_preferences_need_reconcile(paths)
    reconcile_desktop_preferences(paths)
    assert path.read_text() == content


def test_direct_execution_follows_user_symlink(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    path = paths.desktop_dir.parent / ".config/libfm/libfm.conf"
    path.parent.mkdir(parents=True)
    target = tmp_path / "preferences.conf"
    target.write_text("[config]\nquick_exec=0\n")
    path.symlink_to(target)
    reconcile_desktop_preferences(paths)
    assert path.is_symlink()
    assert "quick_exec=1" in target.read_text()


def test_preference_drift_requires_setup_with_wallpaper_disabled(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    paths.desktop_dir.parent.mkdir(parents=True)
    assert desktop_setup_needs_reconcile(paths, False)
    reconcile_desktop_preferences(paths)
    assert not desktop_setup_needs_reconcile(paths, False)


def test_hides_mounts_on_both_hdmi_outputs_and_existing_profiles(tmp_path):
    paths = AgentPaths.sandbox(tmp_path)
    profile = paths.desktop_dir.parent / ".config/pcmanfm/default"
    profile.mkdir(parents=True)
    first = profile / "desktop-items-HDMI-A-1.conf"
    first.write_text("[*]\nwallpaper=/keep.png\nshow_mounts=1\n[icon]\nx=10\n")
    reconcile_desktop_preferences(paths)
    assert first.read_text() == "[*]\nwallpaper=/keep.png\nshow_mounts=0\n[icon]\nx=10\n"
    assert (profile / "desktop-items-HDMI-A-2.conf").read_text() == "[*]\nshow_mounts=0\n"
    assert not desktop_preferences_need_reconcile(paths)
