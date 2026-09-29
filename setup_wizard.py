#!/usr/bin/env python3
"""
ExtDash — Setup Wizard (Linux)

Інтерактивно знаходить усі сенсори вентиляторів і температур через
`sensors -j` (lm-sensors) і дозволяє вибрати потрібні номером, замість
ручного редагування bash-скриптів.

Вимоги:
    sudo apt install lm-sensors
    sudo sensors-detect   (один раз, відповідай "yes" на типові питання)

Запуск:
    python3 setup_wizard.py
"""

import json
import os
import subprocess
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sensor_config.json")


def fetch_sensors():
    try:
        result = subprocess.run(
            ["sensors", "-j"], capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("\n❌ Команда 'sensors' не знайдена.")
        print("   Встанови: sudo apt install lm-sensors")
        print("   Потім один раз: sudo sensors-detect")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Помилка запуску 'sensors -j': {e}")
        sys.exit(1)


def collect_readings(data, keyword_filters=None, exact_suffix=None):
    """
    Збирає всі показники (fanN_input, tempN_input тощо) з дерева sensors -j.
    exact_suffix, якщо задано (наприклад "_input"), відфільтровує лише
    ключі саме з таким закінченням — прибирає зайві *_min/*_max/*_alarm.
    Повертає список {"chip": ..., "label": ..., "key": ..., "value": ...}
    """
    results = []
    for chip, chip_data in data.items():
        if not isinstance(chip_data, dict):
            continue
        for section, section_data in chip_data.items():
            if not isinstance(section_data, dict):
                continue
            for key, value in section_data.items():
                if keyword_filters and not any(kw in key.lower() for kw in keyword_filters):
                    continue
                if exact_suffix and not key.endswith(exact_suffix):
                    continue
                results.append({
                    "chip": chip,
                    "label": section,
                    "key": key,
                    "value": value,
                })
    return results


def choose_fan(items, prompt):
    """Обирає вентилятор і завжди просить RPM-калібрування (мін/макс).
    Дашборд рахує % з реальних обертів: (RPM - мін) / (макс - мін)."""
    sensor = choose_one(items, prompt)
    if sensor is None:
        return None

    print(f"   Поточне значення: {sensor['value']} RPM")
    print("   Вкажи діапазон обертів цього вентилятора:")
    print("   мінімум — на холостому ході, максимум — на повній швидкості.")
    print("   (Можна взяти зі специфікації, BIOS/UEFI або з іншої програми моніторингу.)")

    def ask_rpm(label):
        while True:
            raw = input(f"   {label} RPM: ").strip()
            try:
                value = int(raw)
                if value >= 0:
                    return value
            except ValueError:
                pass
            print("   Потрібно ціле число, 0 або більше.")

    while True:
        min_rpm = ask_rpm("Мінімальні")
        max_rpm = ask_rpm("Максимальні")
        if max_rpm > min_rpm:
            break
        print("   Максимум має бути більшим за мінімум, введи обидва значення ще раз.")

    return {
        "chip": sensor["chip"],
        "label": sensor["label"],  # справжня назва секції в sensors -j, за нею шукається сенсор
        "key": sensor["key"],
        "min_rpm": min_rpm,
        "max_rpm": max_rpm,
    }


def choose_one(items, prompt, allow_skip=True):
    """Показує пронумерований список, повертає обраний ПОВНИЙ запис (з value) або None."""
    if not items:
        print("   (нічого не знайдено цього типу)")
        return None

    print(f"\n{prompt}")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item['chip']} / {item['label']} ({item['key']}) — {item['value']}")
    if allow_skip:
        print(f"  [0] Пропустити (не використовувати)")

    while True:
        choice = input("Твій вибір (номер): ").strip()
        if allow_skip and choice == "0":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]  # повний запис: chip, label, key, value
        except ValueError:
            pass
        print("   Невірний номер, спробуй ще раз.")


def choose_temp(items, prompt):
    """Обирає температурний сенсор і повертає лише {chip, label, key} для конфігу."""
    sensor = choose_one(items, prompt)
    if sensor is None:
        return None
    return {"chip": sensor["chip"], "label": sensor["label"], "key": sensor["key"]}


def choose_network_interface():
    """Знаходить мережеві адаптери ПК (крім loopback) і дає обрати, який
    моніторити на дашборді. Якщо кандидат один — просто підтверджує його."""
    result = subprocess.run(
        ["ip", "-brief", "link", "show"], capture_output=True, text=True
    )
    lines = result.stdout.strip().splitlines()
    candidates = [line.split()[0] for line in lines if line.split()[0] != "lo"]

    if not candidates:
        print("⚠️  Мережевих інтерфейсів не знайдено.")
        return None

    if len(candidates) == 1:
        iface = candidates[0]
        print(f"Знайдено один мережевий інтерфейс: {iface}")
        confirm = input(f"Використати '{iface}'? [Y/n]: ").strip().lower()
        return iface if confirm in ("", "y", "yes", "т", "так") else None

    print("Знайдено декілька мережевих інтерфейсів:")
    for i, name in enumerate(candidates, 1):
        print(f"  [{i}] {name}")
    print("  [0] Пропустити")
    choice = input("Оберіть номер: ").strip()
    try:
        choice = int(choice)
    except ValueError:
        return None
    if choice == 0 or not (1 <= choice <= len(candidates)):
        return None
    return candidates[choice - 1]


def main():
    print("=" * 60)
    print("ExtDash — Майстер налаштування сенсорів (Linux)")
    print("=" * 60)

    data = fetch_sensors()

    fans = collect_readings(data, keyword_filters=["fan"], exact_suffix="_input")
    temps = collect_readings(data, keyword_filters=["temp"], exact_suffix="_input")

    config = {}

    def remaining(items, used_keys):
        """Прибирає вже обрані сенсори зі списку, щоб не призначити той самий фен двічі."""
        return [i for i in items if (i["chip"], i["key"]) not in used_keys]

    used = set()

    print("\n--- ВЕНТИЛЯТОРИ ---")
    print("Обери CPU-кулер:")
    config["cpu_fan"] = choose_fan(fans, "Список знайдених вентиляторів:")
    if config["cpu_fan"]:
        used.add((config["cpu_fan"]["chip"], config["cpu_fan"]["key"]))

    print("\nТепер корпусні вентилятори — по одному. [0] завершує список у будь-який момент.")
    case_fans = []
    while True:
        available = remaining(fans, used)
        fan = choose_fan(available, f"Корпусний вентилятор #{len(case_fans) + 1} (список каналів, що лишились):")
        if fan is None:
            break
        default_label = f"Case Fan {len(case_fans) + 1}"
        custom = input(f"   Назва для дашборду (Enter — '{default_label}'): ").strip()
        fan["display_label"] = custom if custom else default_label  # назва на дашборді; "label" лишається справжнім
        case_fans.append(fan)
        used.add((fan["chip"], fan["key"]))
        if not remaining(fans, used):
            print("   (усі знайдені канали вже призначені)")
            break
    config["case_fans"] = case_fans

    print("\n--- ТЕМПЕРАТУРИ ---")
    print("Обери сенсор CPU:")
    config["cpu_temp"] = choose_temp(temps, "Список знайдених температур:")

    print("\nОбери сенсор VRM (якщо є):")
    config["vrm_temp"] = choose_temp(temps, "Список температур:")

    print("\nОбери сенсор PCH (якщо є):")
    config["pch_temp"] = choose_temp(temps, "Список температур:")

    print("\n--- МЕРЕЖА ---")
    print("Мережевий інтерфейс для моніторингу трафіку:")
    config["network_interface"] = choose_network_interface()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✅ Готово! Конфігурацію збережено у {CONFIG_PATH}")
    print("=" * 60)
    print("\nОбрані сенсори:")
    for key, val in config.items():
        if key == "network_interface":
            print(f"  network_interface: {val if val else '(не обрано)'}")
            continue
        if key == "case_fans":
            if not val:
                print("  case_fans: (жодного не обрано)")
                continue
            for fan in val:
                print(f"  case_fan '{fan['display_label']}': {fan['chip']} / {fan['key']}, RPM-діапазон {fan['min_rpm']}-{fan['max_rpm']}")
            continue
        if val is None:
            print(f"  {key}: (пропущено)")
        elif "min_rpm" in val:
            print(f"  {key}: {val['chip']} / {val['label']} ({val['key']}), RPM-діапазон {val['min_rpm']}-{val['max_rpm']}")
        else:
            print(f"  {key}: {val['chip']} / {val['label']} ({val['key']})")

    print("\n⚠️  Примітка: GPU-дані (навантаження/температура/VRAM/вентилятор)")
    print("   на Linux беруться напряму з Glances (через nvidia-ml-py),")
    print("   тому в цьому майстрі не налаштовуються окремо.")


if __name__ == "__main__":
    main()
