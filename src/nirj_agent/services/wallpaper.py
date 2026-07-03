from html import escape

from nirj_agent.storage.files import write_bytes
from nirj_agent.storage.paths import AgentPaths


WALLPAPER_TEXT = {
    "ready": "Ready",
    "updating": "Updating - Do Not Power Off",
    "failed": "Update Failed - See JAMS Dashboard",
}


def set_wallpaper_state(paths: AgentPaths, state: str) -> None:
    text = WALLPAPER_TEXT[state]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">
<rect width="100%" height="100%" fill="#111827"/>
<text x="50%" y="50%" fill="white" font-family="sans-serif" font-size="64"
 text-anchor="middle" dominant-baseline="middle">{escape(text)}</text>
</svg>\n"""
    write_bytes(paths.generated_dir / "wallpaper.svg", svg.encode())
    write_bytes(paths.root / "state/wallpaper-state.txt", f"{text}\n".encode())
