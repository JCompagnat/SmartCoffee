
# initialize application
from flask import Flask, jsonify, render_template, request, url_for

import time, math
import RPi.GPIO as GPIO
import max31865
import random, json
app = Flask(__name__)


@app.route('/')  # the default is GET only
def index():
	return render_template('index.html')


@app.route('/manualoperations')
def ManualOperations():
	return render_template('manualoperations.html')


@app.route('/plex')
def plex():
	return render_template('plex.html')


@app.route('/_get_temp')
def _get_temp():

	#tempC=random.randint(30, 110)
	max = max31865.max31865()
	tempC = max.readTemp()
	#tempC = max.readTemp()
	GPIO.cleanup()
	return jsonify(temp=tempC)


@app.route('/_set_temp')
def _set_temp():

	GPIO.setmode(GPIO.BCM)
	#target = request.args.get('target', 0, type=int)
	target = 97
	current = _get_temp()
	P = 4

	diff = target-current

	if diff < 0:
		diff = 0

	command = P * diff

	if command > 100:
		command = 100

	GPIO.setup(23,GPIO.OUT)
	p = GPIO.PWM(23, 60)
	p.start(command)

	return


@app.route('/_set_time')
def _set_time():

    tempC=random.randint(30, 110)
    #max = max31865.max31865(csPin,misoPin,mosiPin,clkPin)
    #tempC = max.readTemp()
    return jsonify(temp=tempC)


#@app.route('/_start_pump')
#def _start_pump'():

#    tempC=random.randint(30, 110)
#    #max = max31865.max31865(csPin,misoPin,mosiPin,clkPin)
#    #tempC = max.readTemp()
#    return jsonify(temp=tempC)

# run application
if __name__ == '__main__':
    app.run(host='0.0.0.0')
