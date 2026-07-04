from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from nirj_agent.storage.files import FileStoreError, write_bytes
from nirj_agent.storage.paths import AgentPaths


WALLPAPER_TEXT = {
    "ready": "Ready",
    "updating": "Updating - Do Not Power Off",
    "failed": "Update Failed - See JAMS Dashboard",
}


class WallpaperError(RuntimeError):
    pass


def set_wallpaper_state(
    paths: AgentPaths,
    state: str,
    asset_code: str,
) -> None:
    try:
        text = WALLPAPER_TEXT[state]
    except KeyError as exc:
        raise WallpaperError(f"Unknown wallpaper state: {state}") from exc

    try:
        with Image.open(paths.base_background) as source:
            image = source.convert("RGBA")

        draw = ImageDraw.Draw(image, "RGBA")
        _draw_label(
            draw,
            image.size,
            asset_code,
            font=_load_font(52),
            position="top-right",
        )
        _draw_label(
            draw,
            image.size,
            text,
            font=_load_font(64),
            position="centre",
        )

        output = BytesIO()
        image.convert("RGB").save(output, format="PNG")
        write_bytes(paths.generated_dir / "wallpaper.png", output.getvalue())
        write_bytes(paths.root / "state/wallpaper-state.txt", f"{text}\n".encode())
    except (OSError, ValueError, FileStoreError) as exc:
        raise WallpaperError(f"Could not generate wallpaper: {exc}") from exc


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def _draw_label(
    draw: ImageDraw.ImageDraw,
    image_size: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    position: str,
) -> None:
    margin = 48
    padding_x = 24
    padding_y = 14
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    width = right - left
    height = bottom - top

    if position == "top-right":
        x = image_size[0] - margin - width
        y = margin
    else:
        x = (image_size[0] - width) // 2
        y = (image_size[1] - height) // 2

    draw.rounded_rectangle(
        (
            x - padding_x,
            y - padding_y,
            x + width + padding_x,
            y + height + padding_y,
        ),
        radius=16,
        fill=(0, 0, 0, 150),
    )
    draw.text((x, y - top), text, font=font, fill="white")
