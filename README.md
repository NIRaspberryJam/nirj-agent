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

Install into a dedicated virtual environment on the managed device:

```bash
sudo python3 -m venv /opt/nirj-agent
sudo /opt/nirj-agent/bin/python -m pip install .
```

Production commands omit `--root` and use the real system locations:

```bash
sudo /opt/nirj-agent/bin/nirj-agent get-config
/opt/nirj-agent/bin/nirj-agent status
sudo /opt/nirj-agent/bin/nirj-agent manifest refresh
sudo /opt/nirj-agent/bin/nirj-agent plan
sudo /opt/nirj-agent/bin/nirj-agent apply
```

`apply` requires root and uses the previously cached manifest. It runs
`apt-get update` only when packages need to be installed, installs missing
packages, removes only obsolete packages previously managed by the agent, and
persists state after every package operation succeeds. It never runs
`autoremove`. The command deliberately rejects `--root` because that option
cannot sandbox apt operations.

The production configuration is read from `/etc/nirj-agent/config.yaml` and
state is read from `/var/lib/nirj-agent/state.yaml`. A systemd unit and the
privileged apply workflow will be added with the provider implementation.
