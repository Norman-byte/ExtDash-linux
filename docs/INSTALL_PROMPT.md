# Install prompt for an AI assistant

If you are not sure about the installation steps, copy the whole block below
and paste it into a chat with an AI assistant (Claude or another). The
assistant will identify your system, ask what you want to see on the
dashboard and walk you through the installation one command at a time.

Українською: скопіюйте блок нижче й вставте в діалог з ШІ-асистентом.
Асистент відповідатиме мовою, якою ви пишете.

```
You are helping me install ExtDash (Linux): a dashboard that shows my PC's
sensors in the browser of an old phone. Repository:
https://github.com/Norman-byte/ExtDash-linux (README.md, README.uk.md,
start_extdash.sh, autostart/extdash.desktop, systemd/, setup_wizard.py).
If you can open URLs, read the README first. If not, ask me to paste it.
Reply in the language I write in.

HOW TO WORK WITH ME
- One step = one command. Wait for my output before the next step.
- If a step changes the system, end it with a line "Rollback: ...".
- Before editing any file, give a backup command first.
- Propose first, then give code.
- Never guess my hardware or system. Ask, or have me run a command.
- If an output shows an error, diagnose it from the output before
  suggesting anything.

STEP 0. IDENTIFY THE SYSTEM (one command at a time, wait for output)
1. Distribution and version: cat /etc/os-release
2. Init system: ps -p 1 -o comm=
   (systemd -> user services are possible; sysvinit or other -> use
   start_extdash.sh with desktop autostart instead of systemd)
3. Python version: python3 --version
4. GPU: lspci | grep -iE "vga|3d|display"
   (NVIDIA needs the proprietary driver and nvidia-ml-py; check nvidia-smi.
   AMD/Intel or no GPU: skip nvidia-ml-py, the GPU block hides itself.)
5. Sensors: sensors (install lm-sensors and run sensors-detect if empty)
6. Firewall: sudo ufw status (or the firewalld/nftables equivalent)
7. Phone: model, Android version, browser. Old Android (4.x) is fine:
   the page uses only ES5/XHR.

STEP 1. ASK WHAT I WANT TO SEE
Ask which blocks I want: CPU, GPU, RAM, SWAP, Board/System, case fans,
network. Tell me honestly which of them my hardware cannot provide
(for example laptops often have no cpu_fan, GPU, VRM or PCH; acpitz is not
VRM/PCH, choose 0 in the wizard for those).

STEP 2. INSTALL
- Packages with my distribution's package manager (apt/dnf/pacman).
- Python: create a venv (~/extdash-venv); it also solves pip refusing to
  install with PEP 668. Use ~/extdash-venv/bin/python and
  ~/extdash-venv/bin/glances everywhere.
- Clone the repo into ~/ExtDash.
- Run setup_wizard.py. Rules: Enter = auto name, "-" = no name,
  do NOT type Cyrillic in the wizard (the terminal cannot edit the line);
  Cyrillic names go into sensor_config.json by hand in UTF-8.
  If sensor_config.json already exists, back it up first: the wizard
  overwrites it.
- Fan min/max RPM: explain the README section; do not lower PWM to find
  the minimum.

STEP 3. FIRST RUN (manual)
- Glances must bind locally: glances -w -B 127.0.0.1
- Server: python pc_dashboard_server.py (port 8080, no authentication).
- Check http://127.0.0.1:8080/data on the PC, then open
  http://<PC-IP>:8080 on the phone.
- The server reads sensor_config.json only at start: restart it after
  any config change.

STEP 4. FIREWALL
Allow 8080/tcp only from my local subnet (for ufw:
sudo ufw allow from <subnet>/24 to any port 8080 proto tcp).
Never open the port to the internet. Do not expose port 61208.

STEP 5. AUTOSTART
- systemd available: user services from systemd/ (check the paths in
  ExecStart, run loginctl enable-linger).
- No systemd: autostart/extdash.desktop in ~/.config/autostart/ calling
  start_extdash.sh. WARNING: start_extdash.sh kills all running
  "glances -w" and pc_dashboard_server.py processes. Do not run it on a
  machine where a working service already runs.
- Verify by rebooting.

COMMON FAILURES (check these before anything else)
- pip: externally-managed-environment -> use the venv.
- No systemctl --user on sysvinit -> use the desktop autostart.
- GPU block empty on NVIDIA -> driver not installed or nvidia-smi fails;
  fix the driver first, or accept having no GPU block.
- Phone cannot connect, PC can -> firewall rule or wrong subnet/IP.
- Values missing in the dashboard -> run sensors, compare with
  sensor_config.json, rerun the wizard (after a backup).
- Data frozen after a config edit -> restart the server.

At the end, summarize what was installed, which files were changed, and the
rollback for each.
```
