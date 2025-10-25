# -*- coding: utf-8 -*-
from flask import Flask, jsonify, render_template, request, url_for, session
import time
import random
import multiprocessing
from simple_pid import PID
import jsonpickle
import logging
import sys

# ==========================
# Platform-agnostic imports
# ==========================
try:
    import RPi.GPIO as GPIO
    import max31865
except (ImportError, RuntimeError):
    import mock_gpio as GPIO
    import mock_max31865 as max31865

# =============================
# Global app + shared data
# =============================
application = Flask(__name__)
application.secret_key = 'BAD_SECRET_KEY'
manager = None
shardedData = None
worker_processes = []

# ====================
# Shared data defaults
# ====================
def initialize_shared_data(shared):
    shared['pid_p'] = 0
    shared['pid_i'] = 0
    shared['pid_d'] = 0
    shared['pid_control'] = 0
    shared['brewTime'] = 0
    shared['waterTemp'] = 0
    shared['setTemp'] = 97.5

# ===================
# Background workers
# ===================
def pid(shared):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19, GPIO.OUT)
    pwm = GPIO.PWM(19, 60)
    pwm.start(0)

    pid_controller = PID(2, 0.05, 1.0, setpoint=shared['setTemp'])
    pid_controller.output_limits = (0, 100)
    tempSensor = max31865.max31865()

    while True:
        if pid_controller.setpoint != shared['setTemp']:
            pid_controller.setpoint = shared['setTemp']

        try:
            waterTemp = tempSensor.readTemp()
            waterTemp = round(waterTemp, 1)
        except Exception:
            waterTemp = round(random.uniform(85.0, 105.0), 1)

        control = pid_controller(waterTemp)
        pwm.ChangeDutyCycle(control)

        p, i, d = pid_controller.components
        shared['pid_p'] = p
        shared['pid_i'] = i
        shared['pid_d'] = d
        shared['pid_control'] = control
        shared['waterTemp'] = waterTemp

        time.sleep(1)

def brew(shared):
    while True:
        if shared['brewTime'] > 0:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(26, GPIO.OUT)
            GPIO.output(26, 1)
            while shared['brewTime'] > 0:
                time.sleep(1)
                shared['brewTime'] -= 1
            GPIO.output(26, 0)
        time.sleep(0.5)

# ================
# Flask routes
# ================
@application.route('/', methods=['GET'])
def index():
    return render_template('manualoperations.html')

def ensure_shared_data():
    """Make sure the shared manager/dict are initialized."""
    global shardedData
    if shardedData is None:
        setup_application()


@application.route('/_get_temp')
def _get_temp():
    ensure_shared_data()
    temp = shardedData.get('waterTemp', round(random.uniform(85.0, 105.0), 1))
    return jsonify(
        temp=temp,
        commandP=shardedData.get('pid_p', 0),
        commandI=shardedData.get('pid_i', 0),
        commandD=shardedData.get('pid_d', 0),
        commandPWM=shardedData.get('pid_control', 0),
        brew=shardedData.get('brewTime', 0),
        setTemp=shardedData.get('setTemp', 97.5)
    )

@application.route('/_brew')
def _brew():
    ensure_shared_data()
    shardedData['brewTime'] = 20
    return jsonify(temp=shardedData['brewTime'])

@application.route('/_purge')
def _purge():
    ensure_shared_data()
    shardedData['brewTime'] = 1
    return jsonify(temp=shardedData['brewTime'])

@application.route('/_setTemp110')
def _setTemp110():
    ensure_shared_data()
    shardedData['setTemp'] = 110
    return jsonify(temp=shardedData['setTemp'])

@application.route('/_setTemp975')
def _setTemp975():
    ensure_shared_data()
    shardedData['setTemp'] = 97.5
    return jsonify(temp=shardedData['setTemp'])

# =========================
# Setup function for Apache
# =========================
def setup_application():
    global manager, shardedData
    if manager is None:
        manager = multiprocessing.Manager()
        shardedData = manager.dict()
        initialize_shared_data(shardedData)
    elif shardedData is None:
        shardedData = manager.dict()
        initialize_shared_data(shardedData)

# ================
# Manual Start
# ================
def start_workers():
    global worker_processes
    ensure_shared_data()

    # Avoid spawning multiple copies when the dev server reloads
    alive_workers = [proc for proc in worker_processes if proc.is_alive()]
    worker_processes = alive_workers
    if worker_processes:
        return

    context = multiprocessing.get_context('spawn')
    w1 = context.Process(target=pid, args=(shardedData,))
    w2 = context.Process(target=brew, args=(shardedData,))
    w1.daemon = True
    w2.daemon = True
    w1.start()
    w2.start()
    worker_processes.extend([w1, w2])


@application.before_first_request
def _bootstrap_workers():
    start_workers()

# ================
# App runner
# ================
if __name__ == '__main__':
    multiprocessing.set_start_method("spawn")
    setup_application()
    start_workers()
    application.run(debug=True)
