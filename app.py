#!/usr/bin/env python3
"""SmartCoffee HMI — Raspberry Pi Espresso Machine Controller with PID"""

import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO
from simple_pid import PID

# ── Hardware abstraction ──────────────────────────────────────────────────────
try:
    import RPi.GPIO as GPIO
    ON_PI = True
except (ImportError, RuntimeError):
    import mock_gpio as GPIO
    ON_PI = False

try:
    from max31865 import max31865 as TempSensor
    REAL_SENSOR = True
except Exception:
    from mock_max31865 import max31865 as TempSensor
    REAL_SENSOR = False

# ── Configuration ─────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "pid": {
        "kp": 2.0,
        "ki": 0.05,
        "kd": 1.0,
        "setpoint": 97.5,
        "sample_time": 1.0
    },
    "brew": {
        "brew_duration": 25,
        "purge_duration": 3,
        "pre_infusion_enabled": False,
        "pre_infusion_time": 4
    },
    "safety": {
        "max_temp": 115.0,
        "emergency_shutoff": True
    },
    "sensor": {
        "cs_pin": 4,
        "miso_pin": 9,
        "mosi_pin": 10,
        "clk_pin": 11
    },
    "hardware": {
        "heater_pin": 19,
        "relay_pin": 26,
        "pwm_frequency": 1
    }
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            cfg = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
            for section, values in saved.items():
                if section in cfg and isinstance(values, dict):
                    cfg[section].update(values)
            return cfg
        except Exception:
            pass
    return {k: dict(v) for k, v in DEFAULT_CONFIG.items()}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Application state ─────────────────────────────────────────────────────────
config = load_config()
_lock = threading.Lock()
_state = {
    "current_temp": 0.0,
    "target_temp": config["pid"]["setpoint"],
    "pid_output": 0.0,
    "pid_p": 0.0,
    "pid_i": 0.0,
    "pid_d": 0.0,
    "brew_time_remaining": 0,
    "brew_phase": "idle",   # idle | pre_infusion | brewing | purging | done
    "sensor_ok": False,
    "heater_enabled": True,
    "uptime": 0,
}

# ── Flask + SocketIO ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(16)
sio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
log = logging.getLogger("smartcoffee")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# ── Hardware globals ──────────────────────────────────────────────────────────
_pwm = None
_sensor = None


def _init_hardware():
    global _pwm, _sensor
    hw = config["hardware"]
    s = config["sensor"]

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(hw["heater_pin"], GPIO.OUT)
    GPIO.setup(hw["relay_pin"], GPIO.OUT)
    GPIO.output(hw["relay_pin"], GPIO.LOW)

    _pwm = GPIO.PWM(hw["heater_pin"], hw["pwm_frequency"])
    _pwm.start(0)

    _sensor = TempSensor(
        csPin=s["cs_pin"],
        misoPin=s["miso_pin"],
        mosiPin=s["mosi_pin"],
        clkPin=s["clk_pin"],
    )
    log.info("Hardware initialised (Pi=%s, real sensor=%s)", ON_PI, REAL_SENSOR)


# ── PID worker thread ─────────────────────────────────────────────────────────
_stop = threading.Event()


def _pid_loop():
    pid = PID(
        Kp=config["pid"]["kp"],
        Ki=config["pid"]["ki"],
        Kd=config["pid"]["kd"],
        setpoint=config["pid"]["setpoint"],
        output_limits=(0, 100),
        sample_time=config["pid"]["sample_time"],
    )
    t0 = time.time()

    while not _stop.is_set():
        t_start = time.time()

        with _lock:
            target = _state["target_temp"]
            heater_on = _state["heater_enabled"]

        pid.setpoint = target
        pid.tunings = (config["pid"]["kp"], config["pid"]["ki"], config["pid"]["kd"])

        try:
            temp = _sensor.readTemp()
            sensor_ok = True
        except Exception as exc:
            log.warning("Sensor read error: %s", exc)
            with _lock:
                temp = _state["current_temp"]
            sensor_ok = False

        # Safety shutoff
        if (
            temp > config["safety"]["max_temp"]
            and config["safety"]["emergency_shutoff"]
        ):
            output = 0.0
            log.warning("Emergency shutoff — temp %.1f°C > max %.1f°C", temp, config["safety"]["max_temp"])
        elif not heater_on:
            output = 0.0
        else:
            output = pid(temp) if sensor_ok else 0.0

        output = max(0.0, min(100.0, output))
        _pwm.ChangeDutyCycle(output)

        # Feed heater power back into mock sensor thermal model
        if hasattr(_sensor, "set_heater_power"):
            _sensor.set_heater_power(output)

        p_term, i_term, d_term = pid.components

        with _lock:
            _state["current_temp"] = round(temp, 2)
            _state["pid_output"] = round(output, 1)
            _state["pid_p"] = round(p_term, 3)
            _state["pid_i"] = round(i_term, 3)
            _state["pid_d"] = round(d_term, 3)
            _state["sensor_ok"] = sensor_ok
            _state["uptime"] = int(time.time() - t0)

        elapsed = time.time() - t_start
        _stop.wait(max(0.0, config["pid"]["sample_time"] - elapsed))


# ── Brew worker thread ────────────────────────────────────────────────────────

def _brew_loop():
    relay_pin = config["hardware"]["relay_pin"]

    while not _stop.is_set():
        with _lock:
            phase = _state["brew_phase"]
            remaining = _state["brew_time_remaining"]

        if phase in ("pre_infusion", "brewing", "purging"):
            GPIO.output(relay_pin, GPIO.HIGH)
            if remaining > 0:
                with _lock:
                    _state["brew_time_remaining"] -= 1
                    remaining = _state["brew_time_remaining"]

                if remaining <= 0:
                    # Transition pre-infusion → brewing
                    if phase == "pre_infusion":
                        with _lock:
                            _state["brew_phase"] = "brewing"
                            _state["brew_time_remaining"] = config["brew"]["brew_duration"]
                    else:
                        GPIO.output(relay_pin, GPIO.LOW)
                        with _lock:
                            _state["brew_phase"] = "idle"
            else:
                GPIO.output(relay_pin, GPIO.LOW)
                with _lock:
                    _state["brew_phase"] = "idle"
        else:
            GPIO.output(relay_pin, GPIO.LOW)

        _stop.wait(1.0)


# ── SocketIO emitter task ─────────────────────────────────────────────────────

def _emit_loop():
    while True:
        with _lock:
            payload = dict(_state)
        sio.emit("state", payload)
        sio.sleep(1.0)


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    with _lock:
        return jsonify(dict(_state))


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no data"}), 400
    for section, values in data.items():
        if section in config and isinstance(values, dict):
            config[section].update(values)
    if "pid" in data and "setpoint" in data["pid"]:
        with _lock:
            _state["target_temp"] = float(data["pid"]["setpoint"])
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/brew", methods=["POST"])
def api_brew():
    data = request.get_json(silent=True) or {}
    duration = int(data.get("duration", config["brew"]["brew_duration"]))
    with _lock:
        if _state["brew_phase"] not in ("idle",):
            return jsonify({"error": "brew already active"}), 409
        if config["brew"]["pre_infusion_enabled"]:
            _state["brew_phase"] = "pre_infusion"
            _state["brew_time_remaining"] = config["brew"]["pre_infusion_time"]
        else:
            _state["brew_phase"] = "brewing"
            _state["brew_time_remaining"] = duration
    return jsonify({"ok": True})


@app.route("/api/purge", methods=["POST"])
def api_purge():
    data = request.get_json(silent=True) or {}
    duration = int(data.get("duration", config["brew"]["purge_duration"]))
    with _lock:
        _state["brew_phase"] = "purging"
        _state["brew_time_remaining"] = duration
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    with _lock:
        _state["brew_phase"] = "idle"
        _state["brew_time_remaining"] = 0
    GPIO.output(config["hardware"]["relay_pin"], GPIO.LOW)
    return jsonify({"ok": True})


@app.route("/api/setpoint", methods=["POST"])
def api_setpoint():
    data = request.get_json(silent=True) or {}
    temp = max(80.0, min(130.0, float(data.get("temp", 97.5))))
    with _lock:
        _state["target_temp"] = temp
    config["pid"]["setpoint"] = temp
    save_config(config)
    return jsonify({"ok": True, "setpoint": temp})


@app.route("/api/heater", methods=["POST"])
def api_heater():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", True))
    with _lock:
        _state["heater_enabled"] = enabled
    if not enabled:
        _pwm.ChangeDutyCycle(0)
    return jsonify({"ok": True, "enabled": enabled})


# ── SocketIO events ───────────────────────────────────────────────────────────

@sio.on("connect")
def on_connect():
    log.info("Client connected: %s", request.sid)
    with _lock:
        sio.emit("state", dict(_state), room=request.sid)
    sio.emit("config", config, room=request.sid)


@sio.on("set_config")
def on_set_config(data):
    for section, values in data.items():
        if section in config and isinstance(values, dict):
            config[section].update(values)
    if "pid" in data and "setpoint" in data["pid"]:
        with _lock:
            _state["target_temp"] = float(data["pid"]["setpoint"])
    save_config(config)


@sio.on("command")
def on_command(data):
    cmd = data.get("cmd")
    if cmd == "brew":
        duration = int(data.get("duration", config["brew"]["brew_duration"]))
        with _lock:
            if _state["brew_phase"] == "idle":
                if config["brew"]["pre_infusion_enabled"]:
                    _state["brew_phase"] = "pre_infusion"
                    _state["brew_time_remaining"] = config["brew"]["pre_infusion_time"]
                else:
                    _state["brew_phase"] = "brewing"
                    _state["brew_time_remaining"] = duration
    elif cmd == "purge":
        duration = int(data.get("duration", config["brew"]["purge_duration"]))
        with _lock:
            _state["brew_phase"] = "purging"
            _state["brew_time_remaining"] = duration
    elif cmd == "stop":
        with _lock:
            _state["brew_phase"] = "idle"
            _state["brew_time_remaining"] = 0
        GPIO.output(config["hardware"]["relay_pin"], GPIO.LOW)


# ── Startup ───────────────────────────────────────────────────────────────────

def startup():
    _init_hardware()
    threading.Thread(target=_pid_loop, daemon=True, name="pid-loop").start()
    threading.Thread(target=_brew_loop, daemon=True, name="brew-loop").start()
    sio.start_background_task(_emit_loop)
    log.info("SmartCoffee started on http://0.0.0.0:5000")


if __name__ == "__main__":
    # Skip re-init on Werkzeug auto-reloader child process
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        startup()
    else:
        startup()
    sio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
