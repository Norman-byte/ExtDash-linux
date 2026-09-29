#!/usr/bin/env python3
"""
PC Dashboard Server
Об'єднує дані з Glances API (CPU/GPU/RAM/мережа) та власних bash-скриптів
(вентилятори, VRM/PCH температури) в єдиний JSON для показу на телефоні.

Запуск:
    python3 pc_dashboard_server.py

За замовчуванням слухає на порту 8080, доступний з мережі (0.0.0.0).
"""

import subprocess
import json
import time
import os
from flask import Flask, jsonify, Response, send_file

app = Flask(__name__)

# ── Шляхи проєкту ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Налаштування ──────────────────────────────────────────────────────────
GLANCES_URL = "http://localhost:61208/api/4"

# Сенсори завантажуються з sensor_config.json, який створює setup_wizard.py.
# Формат кожного запису: {"chip": "...", "label": "...", "key": "..."}
SENSOR_CONFIG_PATH = os.path.join(BASE_DIR, "sensor_config.json")


def load_sensor_config():
    if not os.path.exists(SENSOR_CONFIG_PATH):
        print(f"⚠️  Файл {SENSOR_CONFIG_PATH} не знайдено.")
        print("   Спочатку запусти: python3 setup_wizard.py")
        print("   Продовжую без сенсорів материнської плати (будуть null у /data).")
        return {}
    with open(SENSOR_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


SENSORS = load_sensor_config()

NETWORK_INTERFACE = SENSORS.get("network_interface", "enp2s0")
CACHE_TTL = 1.0  # секунд — не смикати sensors/Glances частіше, ніж раз на секунду
_cache = {"data": None, "ts": 0}
_sensors_tree_cache = {"tree": None, "ts": 0}

def fetch_sensors_tree():
    """Завантажує повне дерево `sensors -j` (з коротким кешем)."""
    now = time.time()
    if _sensors_tree_cache["tree"] is not None and (now - _sensors_tree_cache["ts"]) < CACHE_TTL:
        return _sensors_tree_cache["tree"]
    try:
        result = subprocess.run(
            ["sensors", "-j"], capture_output=True, text=True, timeout=3
        )
        tree = json.loads(result.stdout)
        _sensors_tree_cache["tree"] = tree
        _sensors_tree_cache["ts"] = now
        return tree
    except Exception:
        return None


def get_sensor_value(sensor_ref):
    """Повертає числове значення сенсора {"chip", "label", "key"} з sensors -j."""
    if not sensor_ref:
        return None
    tree = fetch_sensors_tree()
    if tree is None:
        return None
    try:
        value = tree[sensor_ref["chip"]][sensor_ref["label"]][sensor_ref["key"]]
        return round(float(value), 1)
    except (KeyError, TypeError, ValueError):
        return None


def get_fan_percent(fan_ref):
    """
    % від реальних обертів вентилятора (не PWM):
        percent = (RPM - MIN) / (MAX - MIN) * 100
    """
    if not fan_ref:
        return None
    raw_rpm = get_sensor_value(fan_ref)
    if raw_rpm is None:
        return None
    min_rpm = fan_ref.get("min_rpm", 0)
    max_rpm = fan_ref.get("max_rpm", 100)
    if max_rpm <= min_rpm:
        return None
    percent = (raw_rpm - min_rpm) / (max_rpm - min_rpm) * 100
    return round(max(0, min(100, percent)), 1)


def fetch_glances(endpoint):
    """Запит до локального Glances REST API через curl (без зайвих залежностей)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "2", f"{GLANCES_URL}/{endpoint}"],
            capture_output=True, text=True, timeout=3
        )
        if result.stdout:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def collect_data():
    """Збирає всі дані з Glances і власних скриптів в один словник."""
    data = {
        "timestamp": time.time(),
        "cpu": {"load_percent": None, "temp_c": None, "fan_percent": None},
        "gpu": {"load_percent": None, "temp_c": None, "fan_percent": None, "vram_percent": None, "name": None},
        "ram": {"used_percent": None},
        "board": {"vrm_temp_c": None, "pch_temp_c": None},
        "case_fans": [],
        "network": {"down_mbps": None, "up_mbps": None},
    }

    # ── CPU (Glances) ──
    cpu = fetch_glances("cpu")
    if cpu:
        data["cpu"]["load_percent"] = round(cpu.get("total", 0), 1)

    # ── CPU температура (обрана в setup_wizard.py) ──
    data["cpu"]["temp_c"] = get_sensor_value(SENSORS.get("cpu_temp"))

    # ── CPU fan % (обраний в setup_wizard.py, RPM → % через калібрування) ──
    data["cpu"]["fan_percent"] = get_fan_percent(SENSORS.get("cpu_fan"))

    # ── GPU (Glances, NVML) ──
    gpu_list = fetch_glances("gpu")
    if gpu_list and len(gpu_list) > 0:
        gpu = gpu_list[0]
        data["gpu"]["name"] = gpu.get("name")
        data["gpu"]["load_percent"] = gpu.get("proc")
        data["gpu"]["temp_c"] = gpu.get("temperature")
        data["gpu"]["fan_percent"] = gpu.get("fan_speed")
        data["gpu"]["vram_percent"] = round(gpu.get("mem", 0), 1) if gpu.get("mem") is not None else None

    # ── RAM (Glances) ──
    mem = fetch_glances("mem")
    if mem:
        data["ram"]["used_percent"] = round(mem.get("percent", 0), 1)

    # ── VRM / PCH температури (обрані в setup_wizard.py) ──
    data["board"]["vrm_temp_c"] = get_sensor_value(SENSORS.get("vrm_temp"))
    data["board"]["pch_temp_c"] = get_sensor_value(SENSORS.get("pch_temp"))

    # ── Корпусні вентилятори — довільна кількість, з sensor_config.json.
    # Кожен елемент: {"chip", "label", "key", "min_rpm", "max_rpm"} — label заданий
    # юзером у setup_wizard.py, кількість елементів не обмежена.
    data["case_fans"] = [
        {"label": fan.get("display_label", fan.get("label", "Case Fan")), "percent": get_fan_percent(fan)}
        for fan in SENSORS.get("case_fans", [])
    ]

    # ── Мережа (Glances) — окремо download/upload, як на референсі ──
    net_list = fetch_glances("network")
    if net_list:
        for iface in net_list:
            if iface.get("interface_name") == NETWORK_INTERFACE:
                recv_bps = iface.get("bytes_recv_rate_per_sec", 0) or 0
                sent_bps = iface.get("bytes_sent_rate_per_sec", 0) or 0
                data["network"]["down_mbps"] = round(recv_bps * 8 / 1_000_000, 2)
                data["network"]["up_mbps"] = round(sent_bps * 8 / 1_000_000, 2)
                break

    return data


@app.route("/data")
def get_data():
    """Головний ендпоінт — віддає JSON з усіма даними. Кешує на CACHE_TTL секунд."""
    now = time.time()
    if _cache["data"] is None or (now - _cache["ts"]) > CACHE_TTL:
        _cache["data"] = collect_data()
        _cache["ts"] = now
    return jsonify(_cache["data"])


@app.route("/")
def index():
    """Головна сторінка — HTML-дашборд для телефону (файл ~/ExtDash/index.html)."""
    html_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(html_path):
        return send_file(html_path)
    return Response(
        "<h3>index.html не знайдено в ~/ExtDash/</h3>"
        "<p>Дані все ще доступні тут: <a href='/data'>/data</a></p>",
        mimetype="text/html"
    )


if __name__ == "__main__":
    print("=" * 50)
    print("PC Dashboard Server")
    port = 8080
    print(f"Дані доступні на: http://<IP-цього-ПК>:{port}/data")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
