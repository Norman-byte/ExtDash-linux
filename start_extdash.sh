#!/bin/bash
# ExtDash: запуск Glances і сервера дашборда без systemd.
# Шляхи можна змінити змінними середовища EXTDASH_VENV і EXTDASH_DIR.

VENV="${EXTDASH_VENV:-$HOME/extdash-venv}"
DIR="${EXTDASH_DIR:-$HOME/ExtDash}"
LOGDIR="$HOME/.cache/extdash"
mkdir -p "$LOGDIR"

# Погасити старі копії, щоб не було дублів
pkill -f "glances -w" 2>/dev/null
pkill -f "pc_dashboard_server.py" 2>/dev/null
sleep 1

# Glances слухає лише локально, назовні дані віддає сервер дашборда
nohup "$VENV/bin/glances" -w -B 127.0.0.1 > "$LOGDIR/glances.log" 2>&1 &

# Чекати до 30 с, поки API Glances відповість
for i in $(seq 1 30); do
    if curl -s --max-time 2 -o /dev/null "http://localhost:61208/api/4/cpu"; then
        break
    fi
    sleep 1
done

nohup "$VENV/bin/python" "$DIR/pc_dashboard_server.py" > "$LOGDIR/server.log" 2>&1 &
