
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


@app.route('/')  # the default is GET only
def index():

	shardedData = manager.dict()

	worker_1 = multiprocessing.Process(name='worker 1', target=pid)
	worker_1.start()
	#session['tempSensor']= max31865.max31865()
	#session['tempSensor'] = max31865.max31865()
	#session['pwm']= GPIO.PWM(23,60)
	#session['pwm'].start(10)
	#session['pwm'].ChangeDutyCycle(30)
	#session['pid'] = PID(20, 0, 200, setpoint=97.5)
	#session['pid'].output_limits = (0, 100)

	#session['tempSensor'] = jsonpickle.encode(session['tempSensor'])
	#session['pwm'] = jsonpickle.encode(session['pwm'])
	#session['pid'] = jsonpickle.encode(session['pid'])
	return render_template('index.html')


@app.route('/manualoperations')
def ManualOperations():
	return render_template('manualoperations.html')


@app.route('/plex')
def plex():
	return render_template('plex.html')


@app.route('/_get_temp')
def _get_temp():
	#GPIO.setmode(GPIO.BCM)
	#GPIO.setmode(GPIO.BCM)
	#GPIO.setup(23, GPIO.OUT)
	#session['pwm'] = jsonpickle.decode(session['pwm'])
	#session['pid'] = jsonpickle.decode(session['pid'])
	#session['tempSensor'] = jsonpickle.decode(session['tempSensor'])
	#tempC=random.randint(30, 110)
	#tempC = session['tempSensor'].readTemp()
	#control = session['pid'](tempC)
	#pwm=GPIO.PWM(23,60)
	#pwm.start(control)
	#session['pwm'].ChangeDutyCycle(control)
	#print(control)
	p = shardedData['pid_p']
	i = shardedData['pid_i']
	d = shardedData['pid_d']
	waterTemp = shardedData['waterTemp']
	#tempC = max.readTemp()
	#session['pwm'] = jsonpickle.encode(session['pwm'])
	#session['pid'] = jsonpickle.encode(session['pid'])
	#session['tempSensor'] = jsonpickle.encode(session['tempSensor'])

	return jsonify(temp=waterTemp, commandP=p, commandI=i, commandD=d)


@app.route('/_set_time')
def _set_time():

    tempC=random.randint(30, 110)
    #max = max31865.max31865(csPin,misoPin,mosiPin,clkPin)
    #tempC = max.readTemp()
    return jsonify(temp=tempC)


def pid():
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(23,GPIO.OUT)
	pwm = GPIO.PWM(23, 60)
	pwm.start(0)

	pid = PID(20, 0, 200, setpoint=97.5)
	pid.output_limits = (0, 100)

	while True:
		tempSensor = max31865.max31865()
		waterTemp = tempSensor.readTemp()

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




#@app.route('/_start_pump')
#def _start_pump'():

#    tempC=random.randint(30, 110)
#    #max = max31865.max31865(csPin,misoPin,mosiPin,clkPin)
#    #tempC = max.readTemp()
#    return jsonify(temp=tempC)

# run application
if __name__ == '__main__':
	app.run(host='0.0.0.0')
