
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


@app.route('/_get_temp')
def _get_temp():

    #tempC=random.randint(30, 110)
	max = max31865.max31865()
    tempC = max.readTemp()
	#tempC = max.readTemp()
    return jsonify(temp=tempC)


@app.route('/_set_temp')
def _set_temp():

	target = request.args.get('target', 0, type=int)

	with open("config.json", "r") as jsonFile:
		config = json.load(jsonFile)

	config["heater"] = target
	print(config)

	with open("config.json", "w") as jsonFile:
		json.dump(config, jsonFile)

	return jsonify(temp=target)


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
