# nirj-agent

Device management agent for Northern Ireland Raspberry Jam devices.

## Persistent layout

Production state lives on a persistent filesystem mounted at `/data`, outside
the root OverlayFS:

```text
/data/nirj/
├── agent-repo/
├── agent-venv/
├── run.sh
├── config/config.yaml
├── state/
│   ├── state.yaml
│   ├── update.json
│   ├── current-manifest.json
│   └── target-manifest.json
├── logs/
└── cache/
```

`install.sh` refuses to install unless `/data` is already a mount point. Disk
partitioning is intentionally a separate image/provisioning responsibility;
guessing a block device in a `curl | bash` installer risks destroying data.

## Bootstrap

The production copy of `install.sh` belongs in `nirj-infra`; the copy in this
repository is the implementation template. Run it as root with the device
identity:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/NIRaspberryJam/nirj-infra/main/install.sh \
  | sudo bash -s -- --asset-id PI5-001 --device-type pi5
```

The installer installs prerequisites, clones `nirj-agent`, creates its venv,
writes the stable `/data/nirj/run.sh`, creates the global CLI symlink, and
enables the root-owned systemd service. Existing device configuration is
preserved.

At each service start, `run.sh` fast-forwards the agent checkout, updates the
venv, runs `nirj-agent boot-prep`, then starts the idle long-running process
with `nirj-agent up`. Exit code 194 means boot preparation requested a reboot;
the runner exits cleanly instead of starting the daemon during shutdown.

## Update and OverlayFS flow

`boot-prep` downloads and validates the target manifest. If it differs from
the current applied manifest while `/` is an overlay, the agent records
`pending_update`, changes the generated wallpaper state, disables OverlayFS,
syncs, and reboots. On the writable boot it records `applying_update`, applies
the manifest, promotes the target manifest to current, restores OverlayFS, and
reboots. Failures persist as `failed` with an error in `update.json`.

Overlay activity is determined from `findmnt -n -o FSTYPE /`; configuration
changes use Raspberry Pi OS's `raspi-config nonint` interface and always
require a reboot.

Useful commands:

```bash
nirj-agent status
nirj-agent update check
sudo nirj-agent update apply
sudo nirj-agent boot-prep

nirj-agent overlay status
sudo nirj-agent overlay enable
sudo nirj-agent overlay disable

nirj-agent config get device.asset_id
sudo nirj-agent config set overlay.enabled true
```

`status`, `update check`, and `config get` do not mutate persistent state.
System changes and configuration writes require root. `update check` downloads
and validates in memory; root-owned boot/update commands persist the target.

The current schema applies APT package state and carries OverlayFS/background
flags. The state machine is structured so files, services, and explicit tasks
can be added as typed manifest providers rather than executing arbitrary data
from a public URL.

## Development

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

Read-only and setup commands can use `--root` to target a sandbox that mirrors
the production `/data/nirj` layout:

```bash
nirj-agent --root .sandbox setup --asset-id TEST-001 --device-type pi5
nirj-agent --root .sandbox status
nirj-agent --root .sandbox config get device.asset_id
nirj-agent --root .sandbox manifest refresh
nirj-agent --root .sandbox plan
```

Commands that invoke APT, OverlayFS, reboot, or production configuration writes
reject `--root` because those effects cannot be filesystem-sandboxed.

Inspect production operation with:

```bash
sudo systemctl status nirj-agent.service
sudo journalctl -u nirj-agent.service -f
```
