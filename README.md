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
require a reboot. `overlay disable` creates
`/data/nirj/state/overlay-disabled-once`, which makes the next `boot-prep`
skip OverlayFS manifest enforcement. The flag is consumed on that boot, so a
later boot restores the manifest's configured OverlayFS state. When enabling
OverlayFS, the agent enforces `overlayroot=tmpfs:recurse=0` so separately
mounted filesystems such as `/data` remain writable and persistent. Before
disabling it, the agent temporarily normalizes the setting to
`overlayroot=tmpfs` for compatibility with `raspi-config`.

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
sudo nirj-agent set-config asset-id PI5-002
```

`status`, `update check`, and `config get` do not mutate persistent state.
System changes and configuration writes require root. `set-config` provides
operator-friendly field names such as `asset-id`, while `config set` accepts
the underlying dotted configuration key. `update check` downloads and validates
in memory; root-owned boot/update commands persist the target.

The current schema applies APT package state and carries OverlayFS/background
flags. When `background.enabled` is true, `boot-prep` renders the current state
and device asset code over the installed base image. An XDG autostart watcher
applies `/data/nirj/cache/generated/wallpaper.png` from inside the logged-in
desktop session. `boot-prep` also reconciles the base image and autostart entry;
when OverlayFS is active, it requests a writable reboot before persisting those
files and then restores the configured overlay state. Raspberry Pi
Desktop/PCManFM, XFCE, and GNOME are supported.

The manifest can also place agent-managed application launchers on the `jam`
user's desktop. Each shortcut must include its corresponding APT package:

```yaml
schema: 1
apt:
  packages:
    - code
    - sonic-pi
desktop:
  shortcuts:
    - vscode
    - sonic-pi
```

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

## Windows bootstrap

Native Windows installations use `C:\ProgramData\nirj` by default and run
`scripts/run-agent.ps1` as a startup Scheduled Task. The runner fast-forwards
the configured branch, updates the virtual environment, and starts
`nirj-agent up`. It intentionally does not run `boot-prep`, because APT,
OverlayFS, and the Linux desktop setup are not applicable on Windows.
At startup, the agent downloads and validates the Windows manifest, promotes
it to the current manifest, and reports `ready: true`. Linux-only manifest
settings are rejected instead of being ignored.

Run the production `install.ps1` from `nirj-infra` in an elevated PowerShell
session:

```powershell
$installer = Join-Path $env:TEMP "install-nirj-agent.ps1"
irm `
  "https://raw.githubusercontent.com/NIRaspberryJam/nirj-infra/main/nirj-agent/install.ps1" `
  -OutFile $installer
& $installer -AssetId "WIN-001"
```

This bootstrap installs and starts the agent but does not yet reconcile
Windows software. Windows package management requires a separate Winget
manifest section and provider.

Inspect the task and follow its log with:

```powershell
Get-ScheduledTask -TaskName "nirj-agent"
Get-Content "C:\ProgramData\nirj\logs\agent.log" -Wait
```
