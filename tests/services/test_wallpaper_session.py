from threading import Event

from nirj_agent.config import DeviceType, create_config, set_config_value
from nirj_agent.services.wallpaper_session import watch_wallpaper
from nirj_agent.storage.paths import AgentPaths


class Desktop:
    def __init__(self, stop_event: Event) -> None:
        self.paths = []
        self.stop_event = stop_event

    def apply(self, path) -> None:
        self.paths.append(path)
        self.stop_event.set()


class SinglePassEvent:
    def __init__(self) -> None:
        self.stopped = False

    def is_set(self) -> bool:
        return self.stopped

    def wait(self, _timeout: float) -> None:
        self.stopped = True


def test_watcher_applies_existing_wallpaper(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-042", DeviceType.PI5, paths.config)
    wallpaper = paths.generated_dir / "wallpaper.png"
    wallpaper.parent.mkdir(parents=True)
    wallpaper.write_bytes(b"png")
    stop_event = Event()
    desktop = Desktop(stop_event)

    watch_wallpaper(paths, stop_event, desktop, poll_interval=0)

    assert desktop.paths == [wallpaper]


def test_watcher_does_not_apply_when_background_is_disabled(tmp_path) -> None:
    paths = AgentPaths.sandbox(tmp_path)
    create_config("PI5-042", DeviceType.PI5, paths.config)
    set_config_value("background.enabled", False, paths.config)
    wallpaper = paths.generated_dir / "wallpaper.png"
    wallpaper.parent.mkdir(parents=True)
    wallpaper.write_bytes(b"png")
    stop_event = SinglePassEvent()
    desktop = Desktop(stop_event)

    watch_wallpaper(paths, stop_event, desktop, poll_interval=0)

    assert desktop.paths == []
