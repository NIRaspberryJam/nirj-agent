from PIL import Image
import pytest

from nirj_agent.services.wallpaper import WallpaperError, set_wallpaper_state
from nirj_agent.storage.paths import AgentPaths


def test_wallpaper_uses_base_image_and_writes_png(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    paths.base_background.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), "#245780").save(paths.base_background)

    set_wallpaper_state(paths, "ready", "PI5-042")

    output = paths.generated_dir / "wallpaper.png"
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (640, 360)
        assert image.getpixel((0, 0)) == (36, 87, 128)
    assert paths.root.joinpath("state/wallpaper-state.txt").read_text() == "Ready\n"


def test_wallpaper_draws_asset_code_in_top_right(tmp_path, monkeypatch) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    paths.base_background.parent.mkdir(parents=True)
    Image.new("RGB", (640, 360), "black").save(paths.base_background)
    labels = []

    def capture_label(_draw, _size, text, *, font, position) -> None:
        labels.append((text, position, font is not None))

    monkeypatch.setattr(
        "nirj_agent.services.wallpaper._draw_label",
        capture_label,
    )

    set_wallpaper_state(paths, "updating", "PI5-042")

    assert labels == [
        ("PI5-042", "top-right", True),
        ("Updating - Do Not Power Off", "centre", True),
    ]


def test_wallpaper_rejects_unknown_state(tmp_path) -> None:
    with pytest.raises(WallpaperError, match="Unknown wallpaper state"):
        set_wallpaper_state(AgentPaths.sandbox(tmp_path), "missing", "PI5-042")
