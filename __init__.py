
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



@app.route('/')  # the default is GET only
def index():

	shardedData['pid_p'] = 0
	shardedData['pid_i'] = 0
	shardedData['pid_d'] = 0
	shardedData['brewTime'] = 0
	shardedData['waterTemp'] = 0
	shardedData['setTemp'] = 97.5

	worker_1 = multiprocessing.Process(name='worker 1', target=pid)
	worker_2 = multiprocessing.Process(name='worker 2', target=brew)

	worker_1.start()
	worker_2.start()

	return render_template('index.html')


@app.route('/manualoperations')
def ManualOperations():
	return render_template('manualoperations.html')


@app.route('/plex')
def plex():
	return render_template('plex.html')


@app.route('/_get_temp')
def _get_temp():

	p = shardedData['pid_p']
	i = shardedData['pid_i']
	d = shardedData['pid_d']
	brewTime = shardedData['brewTime']
	waterTemp = shardedData['waterTemp']
	setTemp = shardedData['setTemp']
	return jsonify(temp=waterTemp, commandP=p, commandI=i,commandD=d,
	brew=brewTime, setTemp=setTemp)


@app.route('/_brew')
def _brew():

    shardedData['brewTime'] = 20
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
	GPIO.setup(23,GPIO.OUT)
	pwm = GPIO.PWM(23, 60)
	pwm.start(0)
	targetTemp = shardedData['setTemp']
	pid = PID(20, 0, 200, setpoint=targetTemp)
	pid.output_limits = (0, 100)
	tempSensor = max31865.max31865()

	while True:

		if targetTemp != shardedData['setTemp']:
			targetTemp = shardedData['setTemp']
			pid.setpoint = targetTemp

		waterTemp = 0
		iteration = 0

		while waterTemp<15 or waterTemp>130:
			waterTemp = tempSensor.readTemp()
			waterTemp = round(waterTemp,1)
			iteration = iteration + 1

			if iteration > 10:
				pwm.ChangeDutyCycle(0)

		control = pid(waterTemp)
		pwm.ChangeDutyCycle(control)

		p, i, d = pid.components
		shardedData['pid_p']=p
		shardedData['pid_i']=i
		shardedData['pid_d']=d
		shardedData['pid_control']=control
		shardedData['waterTemp']=waterTemp

		time.sleep(1)

	return

def brew():

	while True:

		if shardedData['brewTime'] > 0:

			GPIO.setmode(GPIO.BCM)
			GPIO.setup(24,GPIO.OUT)

			while shardedData['brewTime'] > 0:

				maxTemp = shardedData['setTemp'] + 1
				minTemp = shardedData['setTemp'] - 1

				if minTemp <= shardedData['waterTemp'] <= maxTemp:
					GPIO.output(24, 1)
					time.sleep(1)
					shardedData['brewTime'] = shardedData['brewTime']-1

				else:
					GPIO.output(24, 0)

			GPIO.output(24, 0)

		time.sleep(0.5)

	return


#@app.route('/_start_pump')
#def _start_pump'():

#    tempC=random.randint(30, 110)
#    #max = max31865.max31865(csPin,misoPin,mosiPin,clkPin)
#    #tempC = max.readTemp()
#    return jsonify(temp=tempC)

# run application
if __name__ == '__main__':
	app.run(host='0.0.0.0')
