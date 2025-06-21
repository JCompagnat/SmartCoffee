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
# Global Flask app declaration
# =============================
application = Flask(__name__)
application.secret_key = 'BAD_SECRET_KEY'

# Shared data store
manager = multiprocessing.Manager()
shardedData = manager.dict()

# ====================
# Shared data defaults
# ====================
def initialize_shared_data():
    shardedData['pid_p'] = 0
    shardedData['pid_i'] = 0
    shardedData['pid_d'] = 0
    shardedData['brewTime'] = 0
    shardedData['waterTemp'] = 0
    shardedData['setTemp'] = 97.5

# ===================
# Background workers
# ===================
def pid():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19, GPIO.OUT)
    pwm = GPIO.PWM(19, 60)
    pwm.start(0)

    pid_controller = PID(20, 0, 250, setpoint=shardedData['setTemp'])
    pid_controller.output_limits = (0, 100)
    tempSensor = max31865.max31865()

    while True:
        if pid_controller.setpoint != shardedData['setTemp']:
            pid_controller.setpoint = shardedData['setTemp']

        try:
            waterTemp = tempSensor.readTemp()
            waterTemp = round(waterTemp, 1)
        except Exception:
            waterTemp = round(random.uniform(85.0, 105.0), 1)

        control = pid_controller(waterTemp)
        pwm.ChangeDutyCycle(control)

        p, i, d = pid_controller.components
        shardedData['pid_p'] = p
        shardedData['pid_i'] = i
        shardedData['pid_d'] = d
        shardedData['pid_control'] = control
        shardedData['waterTemp'] = waterTemp

        time.sleep(1)

def brew():
    while True:
        if shardedData['brewTime'] > 0:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(26, GPIO.OUT)
            GPIO.output(26, 1)
            while shardedData['brewTime'] > 0:
                time.sleep(1)
                shardedData['brewTime'] -= 1
            GPIO.output(26, 0)
        time.sleep(0.5)

# ================
# Flask routes
# ================
@application.route('/', methods=['GET'])
def index():
    return render_template('manualoperations.html')

@application.route('/_get_temp')
def _get_temp():
    temp = shardedData.get('waterTemp', round(random.uniform(85.0, 105.0), 1))
    return jsonify(
        temp=temp,
        commandP=shardedData.get('pid_p', 0),
        commandI=shardedData.get('pid_i', 0),
        commandD=shardedData.get('pid_d', 0),
        brew=shardedData.get('brewTime', 0),
        setTemp=shardedData.get('setTemp', 97.5)
    )

@application.route('/_brew')
def _brew():
    shardedData['brewTime'] = 20
    return jsonify(temp=shardedData['brewTime'])

@application.route('/_purge')
def _purge():
    shardedData['brewTime'] = 1
    return jsonify(temp=shardedData['brewTime'])

@application.route('/_setTemp110')
def _setTemp110():
    shardedData['setTemp'] = 110
    return jsonify(temp=shardedData['setTemp'])

@application.route('/_setTemp975')
def _setTemp975():
    shardedData['setTemp'] = 97.5
    return jsonify(temp=shardedData['setTemp'])

# ================
# Manual Start
# ================
def start_workers():
    w1 = multiprocessing.Process(target=pid)
    w2 = multiprocessing.Process(target=brew)
    w1.start()
    w2.start()

# ================
# App runner
# ================
if __name__ == '__main__':
    multiprocessing.set_start_method("spawn")
    initialize_shared_data()
    start_workers()
    application.run(debug=True)

# ================
# Apache mod_wsgi init
# ================
if 'mod_wsgi' in sys.modules:
    initialize_shared_data()
    start_workers()
