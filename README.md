# ExtDash — a second screen for monitoring your PC on an old phone

**English** | [Українська](README.uk.md)

Turns any phone with a browser into a live dashboard for a Linux PC:
CPU, GPU, RAM, SWAP, motherboard temperatures, case fans, network.
Data updates in real time; no separate phone app is needed.

This version is for **Linux**. A Windows version is being developed separately.

**Not sure about the installation steps?** At the bottom there is a prompt for an AI assistant: paste it into a chat and the assistant will walk you through step by step, safely (see "Installing with an AI assistant").

## Screenshots

| HTC One S (Android 4.1.1, 2012) | OnePlus 9 (LineageOS) |
|---|---|
| ![HTC One S](docs/screenshots/htc_one_s.png) | ![OnePlus 9](docs/screenshots/oneplus_9.png) |

The same `index.html` opens on a phone from 2012 and on a modern one.

## How it works

```
Phone (browser) ──HTTP──► Flask server (port 8080)
                            ├── Glances API (127.0.0.1:61208): CPU, GPU, RAM, SWAP, network
                            └── lm-sensors (sensors -j): fans, VRM, PCH
```

The `pc_dashboard_server.py` server combines Glances data and `sensors -j`
into a single JSON (`/data`) and serves the `index.html` page. Which sensors
are shown is defined by `sensor_config.json`, which is created by
`setup_wizard.py`.

## What the dashboard shows

| Block | Data |
|---|---|
| CPU | Load %, temperature, fan % |
| GPU | Load %, temperature, fan %, VRAM % (shown only if a GPU is present) |
| RAM | Usage %, with SWAP below it |
| Board & Fans | VRM and PCH temperatures, any number of case fans, network speed (↓/↑) |
| System | Load average (1/5/15 min), uptime, disk usage of `/` (shown only without a GPU, see `system_block`) |

If there is no GPU, the GPU block is hidden: CPU and RAM sit side by side and
the bottom block takes the full width.

If no VRM, PCH or fans are configured (for example on a laptop), the bottom
block is titled **Network** and shows only the network speed.

You can set your own names for the CPU and GPU blocks (see "Installation",
step 3).

Fan percentage is calculated from real RPM:
`(RPM − min) / (max − min)`. This is why the minimum and maximum for each fan
must be set manually (see below).

## Requirements

- Linux, Python 3.10+ (tested on Python 3.12, Linux Mint, and on Python 3.11.2, MX Linux 23.4)
- `lm-sensors` with configured sensors
- Glances 4.x with web mode, Flask
- `nvidia-ml-py` — only for NVIDIA graphics cards (Glances reads GPU data through it)
- PC and phone on the same local network

Tested versions: Glances 4.5.6–4.5.7, Flask 3.1.3, nvidia-ml-py 13.610–13.615.

## Installation

1. System packages and sensors:

   ```bash
   sudo apt install lm-sensors python3-venv curl
   sudo sensors-detect      # answer "yes" to the typical questions
   ```

2. Python dependencies in a virtual environment (also works on distributions
   with PEP 668, where `pip` refuses to install packages system-wide):

   ```bash
   python3 -m venv ~/extdash-venv
   ~/extdash-venv/bin/pip install "glances[web]" flask
   ~/extdash-venv/bin/pip install nvidia-ml-py    # NVIDIA graphics cards only
   ```

   From here on, use `~/extdash-venv/bin/python` and
   `~/extdash-venv/bin/glances` in all commands.

3. Download the project into `~/ExtDash` and run the setup wizard:

   ```bash
   git clone https://github.com/Norman-byte/ExtDash-linux.git ~/ExtDash
   cd ~/ExtDash
   ~/extdash-venv/bin/python setup_wizard.py
   ```

   The wizard lists all detected fans and temperatures; you choose the CPU
   cooler, case fans, the CPU/VRM/PCH sensors and the network interface. The
   result is written to `sensor_config.json` next to the script.

   - Choose fans by section name (`System Fan #N`), not by position in the
     list: the list is renumbered after every selection.
   - CPU/GPU names: Enter — the name is detected automatically (no key is
     written to the file), your own name — type the text, `-` — the block has
     no name.
  - **System block:** Enter — automatic (shown only when there is no GPU, no
    key is written), `y` — always show, `n` — never show (the wizard writes
    `"system_block": true` or `false`).
   - **Do not type Cyrillic in the wizard:** line editing in the terminal does
     not work correctly with it. Put a Cyrillic name into `sensor_config.json`
     by hand (UTF-8), for example `"cpu_name": "Ноут ASUS"`.
   - If you do not have a sensor (for example VRM or PCH on a laptop), choose
     0. The `acpitz` sensor is not a VRM or PCH.
   - **The wizard overwrites `sensor_config.json`.** If you already have a
     working configuration, make a copy of it first.

4. Manual run (for testing):

   ```bash
   cd ~/ExtDash
   ~/extdash-venv/bin/glances -w -B 127.0.0.1 &
   ~/extdash-venv/bin/python pc_dashboard_server.py
   ```

   `-B 127.0.0.1` makes Glances listen locally only (port 61208); the phone
   connects only to the server on port 8080.

   Open `http://<your-PC-IP>:8080` on the phone.
   JSON data: `http://<your-PC-IP>:8080/data`.

   The server reads `sensor_config.json` only at startup: restart the server
   after any configuration change.

## Measuring fan RPM

The wizard asks for the minimum and maximum RPM of each fan. There are no
defaults: the range depends on the model and size, and a wrong range gives
wrong percentages.

- **Maximum** — RPM at full speed. For case fans the wizard can measure it
  itself: with your consent (`sudo` is required) the fan is set to 100% for a
  few seconds, after which the previous control mode is restored. This works
  if the driver exposes `pwmN` control for that fan (tested on nct6687). For
  the CPU fan and the pump, auto-measurement is not performed: enter the
  maximum manually (specification, BIOS/UEFI or another monitoring program).
  If auto-measurement fails, the wizard also asks you to enter the value
  manually.
- **Minimum** — always entered manually: the lowest RPM at which the fan
  spins stably. Idle RPM can be higher than the real minimum, so do not use
  it. Sources: specification, BIOS/UEFI or another monitoring program. If the
  minimum is unknown, enter 0 and the percentage is calculated from the
  maximum. For fans that stop completely, the minimum is also 0.
- Current RPM is shown in the wizard's list and in the output of `sensors`.

Do not determine the minimum by lowering PWM yourself: some fans stop and do
not start again on their own.

The maximum must be greater than the minimum.

## Autostart

Choose the option that matches your init system (`ps -p 1 -o comm=`).

### A) systemd (user mode)

The `systemd/` folder contains service templates. They assume the project is
in `~/ExtDash`, and Glances and Python are in the `~/extdash-venv` venv. If
that is not the case, fix the paths in `ExecStart`.

```bash
mkdir -p ~/.config/systemd/user
cp systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now glances-extdash.service pc-dashboard-extdash.service
loginctl enable-linger "$USER"     # so the services start without a login
```

Check: `systemctl --user status pc-dashboard-extdash.service`.

### B) without systemd (sysvinit and others)

The `start_extdash.sh` script starts Glances (with `-B 127.0.0.1`) and the
server, and the `autostart/extdash.desktop` file calls it when you log in to
a graphical session (with a 10-second delay). The project must be in
`~/ExtDash`.

```bash
mkdir -p ~/.config/autostart
cp ~/ExtDash/autostart/extdash.desktop ~/.config/autostart/
```

Logs are written to `~/.cache/extdash/`.

**Warning:** `start_extdash.sh` stops all running `glances -w` and
`pc_dashboard_server.py` processes and then starts them again. Do not run it
on a machine where a systemd service or another working instance is running.

## Security

The server listens on `0.0.0.0:8080` **without authentication** and exposes
information about the PC's hardware. Use it only on a trusted local network
and do not expose the port to the internet.

Glances listens only on `127.0.0.1:61208` and is not reachable from outside.

If `ufw` is enabled on the PC, allow port 8080 only from your own subnet
(substitute yours):

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8080 proto tcp
```

## Limitations

- The set of sensors depends on the hardware. For example, laptops usually
  have no `cpu_fan`, GPU, VRM or PCH. The `acpitz` sensor is not a VRM or PCH.
- If there is no GPU, the GPU block is hidden.
- The System block (load average, uptime, disk `/`) is shown only when there is
  no GPU. Set `"system_block": true` or `false` in `sensor_config.json` to
  override; no key or `"auto"` means automatic.
- The server reads `sensor_config.json` only at startup.

## GPU temperature on Linux

The Linux version shows the **core (Core)** temperature. NVIDIA does not
expose hotspot/junction temperature through Linux drivers, neither in
`nvidia-smi` nor in NVML. The real die temperature at the hottest point is
usually 10–20 °C higher, so leave a margin below the manufacturer's thermal
limit.

## Installing with an AI assistant

If you are not sure about a step, use the ready-made prompt:
[docs/INSTALL_PROMPT.md](docs/INSTALL_PROMPT.md). Copy its contents and paste
them into a chat with an AI assistant (Claude or another). The assistant will
identify your hardware, ask what you want to see on the dashboard, and guide
you step by step: one command at a time, with a rollback and a backup before
any edits.

## License

MIT — use, modify and distribute freely.

## About the development

The project was built in partnership with Claude (Anthropic): from reviving an
old HTC One S to the Linux backend. Everything was investigated and tested
step by step, including real dead ends (NVIDIA driver limitations on Linux,
discrepancies between PWM and real RPM) and their practical solutions.
