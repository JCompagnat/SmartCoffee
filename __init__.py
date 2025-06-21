import platform
from flask import Flask, jsonify, render_template
import time
import random
import multiprocessing
from simple_pid import PID
import jsonpickle

# Détection automatique de la plateforme
IS_RASPBERRY_PI = platform.system() == 'Linux' and platform.machine().startswith('arm')

# Import GPIO / capteur selon la plateforme
if IS_RASPBERRY_PI:
    import RPi.GPIO as GPIO
    import max31865
else:
    import mock_gpio as GPIO
    import mock_max31865 as max31865

app = None
shardedData = None

def initialize_shared_data(shared_data):
    shared_data['pid_p'] = 0
    shared_data['pid_i'] = 0
    shared_data['pid_d'] = 0
    shared_data['brewTime'] = 0
    shared_data['waterTemp'] = 90
    shared_data['setTemp'] = 97.5

def register_routes(app, shared_data):
    @app.route('/', methods=['GET', 'POST'])
    def index():
        # Choix automatique du bon processus
        if IS_RASPBERRY_PI:
            worker_1 = multiprocessing.Process(name='pid', target=pid, args=(shared_data,))
        else:
            worker_1 = multiprocessing.Process(name='simulator', target=simulate_temperature, args=(shared_data,))
        worker_2 = multiprocessing.Process(name='brew', target=brew, args=(shared_data,))
        worker_1.start()
        worker_2.start()
        return render_template('manualoperations.html')

    @app.route('/_get_temp')
    def _get_temp():
        temp = shared_data.get('waterTemp', 0)
        return jsonify(
            temp=temp,
            commandP=shared_data.get('pid_p', 0),
            commandI=shared_data.get('pid_i', 0),
            commandD=shared_data.get('pid_d', 0),
            brew=shared_data.get('brewTime', 0),
            setTemp=shared_data.get('setTemp', 97.5)
        )

    @app.route('/_brew')
    def _brew():
        shared_data['brewTime'] = 20
        return jsonify(temp=shared_data['brewTime'])

    @app.route('/_purge')
    def _purge():
        shared_data['brewTime'] = 1
        return jsonify(temp=shared_data['brewTime'])

    @app.route('/_setTemp110')
    def _setTemp110():
        shared_data['setTemp'] = 110
        return jsonify(temp=shared_data['setTemp'])

    @app.route('/_setTemp975')
    def _setTemp975():
        shared_data['setTemp'] = 97.5
        return jsonify(temp=shared_data['setTemp'])

def pid(shared_data):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(19, GPIO.OUT)
    pwm = GPIO.PWM(19, 60)
    pwm.start(0)

    pid_controller = PID(20, 0, 250, setpoint=shared_data['setTemp'])
    pid_controller.output_limits = (0, 100)
    tempSensor = max31865.max31865()

    while True:
        if pid_controller.setpoint != shared_data['setTemp']:
            pid_controller.setpoint = shared_data['setTemp']

        isTempValid = False
        while not isTempValid:
            try:
                waterTemp = tempSensor.readTemp()
                waterTemp = round(waterTemp, 1)
                isTempValid = 15 <= waterTemp <= 120
            except Exception:
                isTempValid = False
            time.sleep(0.5)

        if isTempValid:
            control = pid_controller(waterTemp)
            pwm.ChangeDutyCycle(control)
        else:
            pwm.ChangeDutyCycle(0)

        p, i, d = pid_controller.components
        shared_data['pid_p'] = p
        shared_data['pid_i'] = i
        shared_data['pid_d'] = d
        shared_data['pid_control'] = control
        shared_data['waterTemp'] = waterTemp

        time.sleep(1)

def brew(shared_data):
    while True:
        if shared_data['brewTime'] > 0:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(26, GPIO.OUT)
            GPIO.output(26, 1)
            while shared_data['brewTime'] > 0:
                time.sleep(1)
                shared_data['brewTime'] -= 1
            GPIO.output(26, 0)
        time.sleep(0.5)

def simulate_temperature(shared_data):
    base_temp = 90
    direction = 1
    while True:
        current = shared_data.get('waterTemp', base_temp)
        noise = random.uniform(-0.2, 0.2)
        next_temp = current + direction * 0.4 + noise

        if next_temp > 105:
            direction = -1
        elif next_temp < 85:
            direction = 1

        shared_data['waterTemp'] = round(next_temp, 1)
        time.sleep(1)

def start_server():
    global app, shardedData
    app = Flask(__name__)
    app.secret_key = 'BAD_SECRET_KEY'
    manager = multiprocessing.Manager()
    shardedData = manager.dict()
    initialize_shared_data(shardedData)
    register_routes(app, shardedData)
    app.run(host='0.0.0.0', port=5050)

if __name__ == '__main__':
    multiprocessing.set_start_method("spawn")
    start_server()
