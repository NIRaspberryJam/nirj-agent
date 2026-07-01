# nirj-agent

Device management agent for Northern Ireland Raspberry Jam devices.

## Development usage

Create a virtual environment and install the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
```

Use `--root` to run the CLI against an isolated filesystem tree instead of
reading or writing the host's `/etc`, `/var`, `/boot`, and `/usr` paths:

```bash
mkdir -p .sandbox/etc/nirj-agent
mkdir -p .sandbox/var/lib/nirj-agent
nirj-agent --root .sandbox status
nirj-agent --root .sandbox get-config
nirj-agent --root .sandbox manifest refresh
nirj-agent --root .sandbox plan
```

The sandbox layout mirrors the production filesystem. For example, its
configuration belongs at `.sandbox/etc/nirj-agent/config.yaml` and its state
at `.sandbox/var/lib/nirj-agent/state.yaml`.

`manifest refresh` downloads and validates the configured manifest before
atomically caching it. `plan` reads that cached manifest and reports package
changes without installing, removing, or changing any state.

## Production usage

Run the installer as root with the device's asset ID and type:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/NIRaspberryJam/nirj-agent/main/install.sh \
  | sudo bash -s -- --asset-id PI5-001 --device-type pi5
```

Valid device types for this systemd-based installer are `pi5` and `lpt-lx`.
The installer clones the repository into `/opt/nirj-agent/source`, creates a
virtual environment at `/opt/nirj-agent/venv`, creates the initial
configuration, and enables and starts `nirj-agent.service`. Existing
configuration is preserved when the installer is run again.

At every service start, `scripts/run-agent.sh` fast-forwards the checkout,
reinstalls the package, and runs `nirj-agent up`. The agent then refreshes and
applies the configured manifest before remaining active.

Inspect the service with:

```bash
sudo systemctl status nirj-agent.service
sudo journalctl -u nirj-agent.service -f
```

Production commands use `/opt/nirj-agent/venv` and omit `--root`:

```bash
sudo /opt/nirj-agent/venv/bin/nirj-agent get-config
/opt/nirj-agent/venv/bin/nirj-agent status
sudo /opt/nirj-agent/venv/bin/nirj-agent manifest refresh
sudo /opt/nirj-agent/venv/bin/nirj-agent plan
sudo /opt/nirj-agent/venv/bin/nirj-agent apply
sudo /opt/nirj-agent/venv/bin/nirj-agent up
```

`apply` requires root and uses the previously cached manifest. It runs
`apt-get update` only when packages need to be installed, installs missing
packages, removes only obsolete packages previously managed by the agent, and
persists state after every package operation succeeds. It never runs
`autoremove`. The command deliberately rejects `--root` because that option
cannot sandbox apt operations.

`up` is the long-running production command. It requires root, refreshes the
configured manifest, applies it, and then remains running until it receives a
shutdown signal. It deliberately rejects `--root` for the same reason as
`apply`.

The production configuration is read from `/etc/nirj-agent/config.yaml` and
state is read from `/var/lib/nirj-agent/state.yaml`. A systemd unit will be
added with the production installer.
