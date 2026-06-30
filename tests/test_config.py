from importlib import import_module
from pathlib import Path
from uuid import UUID

import pytest
import yaml

from nirj_agent.config import DeviceType, ConfigError, create_config, load_config

cli = import_module("nirj_agent.cli.main")


def write_valid_config(path: Path, device_id: UUID) -> None:
    path.write_text(
        f"""
device:
  id: {device_id}
  asset_id: PI5-001
  type: pi5
manifest:
  source:
    type: github
    repo: NIRaspberryJam/nirj-infra
    path: manifests/pi5.manifest.yaml
    ref: main
overlay:
  enabled: true
background:
  enabled: true
""",
        encoding="utf-8",
    )


def test_load_config(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    device_id = UUID("fc41017d-0937-49f2-a49d-a64164d9cc2e")
    write_valid_config(path, device_id)
    config = load_config(path)
    assert config.device.id == device_id
    assert config.device.asset_id == "PI5-001"
    assert config.device.type == "pi5"
    assert config.manifest.ref == "main"
    assert config.overlay_enabled is True
    assert config.background_enabled is True


def test_load_config_defaults_manifest_ref(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    device_id = UUID("fc41017d-0937-49f2-a49d-a64164d9cc2e")
    write_valid_config(path, device_id)
    contents = path.read_text(encoding="utf-8").replace("    ref: main\n", "")
    path.write_text(contents, encoding="utf-8")
    assert load_config(path).manifest.ref == "main"


def test_load_config_rejects_invalid_uuid(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
device:
  id: not-a-uuid
  asset_id: PI5-001
  type: pi5
manifest:
  source:
    type: github
    repo: NIRaspberryJam/nirj-infra
    path: manifests/pi5.manifest.yaml
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_config(path)


def test_load_config_rejects_missing_required_field(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("device: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_config(path)


def test_create_config_stores_full_uuid(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    config = create_config("PI5-001", DeviceType.PI5, path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    stored_uuid = UUID(raw_config["device"]["id"])
    assert stored_uuid == config.device.id
    assert stored_uuid.version == 4
    assert len(str(stored_uuid)) == 36
    assert config.device.asset_id == "PI5-001"
    assert config.manifest.path == "manifests/pi5.manifest.yaml"

def test_device_type_values() -> None:
    assert [value.value for value in DeviceType] == [
        "pi5",
        "lpt-lx",
        "lpt-win",
    ]

def test_create_config_rejects_unknown_device_type(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    write_valid_config(path, UUID("fc41017d-0937-49f2-a49d-a64164d9cc2e"))
    contents = path.read_text().replace("type: pi5", "type: toaster")
    path.write_text(contents)

    with pytest.raises(ConfigError, match="toaster"):
        load_config(path)

def test_create_config_does_not_replace_existing_uuid(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    first = create_config("PI5-001", DeviceType.PI5, path)

    with pytest.raises(ConfigError, match="already exists"):
        create_config("PI5-002", DeviceType.PI5, path)

    assert load_config(path).device.id == first.device.id

def test_setup_creates_sandbox_config(tmp_path: Path, capsys) -> None:
    result = cli.main([
        "--root",
        str(tmp_path),
        "setup",
        "--asset-id",
        "PI5-001",
        "--device-type",
        "pi5",
    ])

    config = load_config(tmp_path / "etc/nirj-agent/config.yaml")

    assert result == 0
    assert config.device.asset_id == "PI5-001"
    assert config.device.type is DeviceType.PI5
