
# initialize application
from flask import Flask, jsonify, render_template, request, url_for, session

import time, math
import RPi.GPIO as GPIO
import max31865
import random, json
from simple_pid import PID
import jsonpickle
import multiprocessing

app = Flask(__name__)
app.secret_key = 'BAD_SECRET_KEY'
manager = multiprocessing.Manager()
shardedData = manager.dict()

def initialize_shared_data():
	shardedData['pid_p'] = 0
	shardedData['pid_i'] = 0
	shardedData['pid_d'] = 0
	shardedData['brewTime'] = 0
	shardedData['waterTemp'] = 0
	shardedData['setTemp'] = 97.5

@app.route('/')  # the default is GET only
def index():
	initialize_shared_data()
	worker_1 = multiprocessing.Process(name='worker 1', target=pid)
	worker_2 = multiprocessing.Process(name='worker 2', target=brew)
	worker_3 = multiprocessing.Process(name='worker 3', target=status)
	worker_1.start()
	worker_2.start()
	worker_3.start()
	return render_template('manualoperations.html')

@app.route('/manualoperations')
def ManualOperations():
    return render_template('manualoperations.html')	

@app.route('/plex')
def plex():
	return render_template('plex.html')

@app.route('/slideshow')
def slideShow():
	return render_template('slideShow.html')

@app.route('/_get_temp')
def _get_temp():
	p = shardedData['pid_p']
	i = shardedData['pid_i']
	d = shardedData['pid_d']
	brewTime = shardedData['brewTime']
	waterTemp = shardedData['waterTemp']
	setTemp = shardedData['setTemp']
	brewLight = shardedData['brewLight']
	return jsonify(temp=waterTemp, commandP=p, commandI=i,commandD=d,
	brew=brewTime, setTemp=setTemp, brewLight=brewLight)


@app.route('/_brew')
def _brew():
    shardedData['brewTime'] = 20
    return jsonify(temp=shardedData['brewTime'])

@app.route('/_purge')
def _purge():
    shardedData['brewTime'] = 1
    return jsonify(temp=shardedData['brewTime'])

@app.route('/_setTemp110')
def _setTemp110():
	shardedData['setTemp'] = 110
	return jsonify(temp=shardedData['setTemp'])

@app.route('/_setTemp975')
def __setTemp975():
	shardedData['setTemp'] = 97.5
	return jsonify(temp=shardedData['setTemp'])

def pid():
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(19,GPIO.OUT)
	pwm = GPIO.PWM(19, 60)
	pwm.start(0)
	targetTemp = shardedData['setTemp']
	pid = PID(20, 0, 250, setpoint=targetTemp)
	pid.output_limits = (0, 100)
	tempSensor = max31865.max31865()

	while True:

		if targetTemp != shardedData['setTemp']:
			targetTemp = shardedData['setTemp']
			pid.setpoint = targetTemp

		waterTemp = 0
		iteration = 0
		isTempValid = False

		while (isTempValid==False):
			waterTemp = tempSensor.readTemp()
			waterTemp = round(waterTemp,1)

			if (waterTemp<15) or (waterTemp>120):
				isTempValid = False

			else:
				isTempValid = True

			iteration = iteration + 1
			time.sleep(0.5)

		if isTempValid == True:
			control = pid(waterTemp)
			pwm.ChangeDutyCycle(control)

		else:
			pwm.ChangeDutyCycle(0)

		p, i, d = pid.components
		shardedData['pid_p']=p
		shardedData['pid_i']=i
		shardedData['pid_d']=d
		shardedData['pid_control']=control
		shardedData['waterTemp']=waterTemp

		time.sleep(1)

def brew():
	while True:
		if shardedData['brewTime'] > 0:
			GPIO.setmode(GPIO.BCM)
			GPIO.setup(26,GPIO.OUT)
			GPIO.output(26, 1)
			while shardedData['brewTime'] > 0:
				time.sleep(1)
				shardedData['brewTime'] -= 1
			GPIO.output(26, 0)

		time.sleep(0.5)
	return

def status():
	while True:
		tempLimit = 0.5
		temp = shardedData['waterTemp']
		target = hardedData['setTemp']
		if target - tempLimit < temp > target + tempLimit:
			shardedData['brewLight'] = 1
		else:
			shardedData['brewLight'] = 0
		time.sleep(0.5)
	return


# run application
if __name__ == '__main__':
	app.run(host='0.0.0.0')
