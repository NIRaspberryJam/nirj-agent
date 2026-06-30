import os
from pathlib import Path

class FileStoreError(RuntimeError):
    pass

def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")

    try:
        with temporary_path.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_path.replace(path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise FileStoreError(f"Unable to write {path}: {exc}") from exc