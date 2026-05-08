"""Mock RPi.GPIO module for development without hardware."""

BCM = "BCM"
OUT = "OUT"
IN = "IN"
HIGH = 1
LOW = 0


class PWM:
    def __init__(self, pin, freq):
        self._pin = pin
        self._dc = 0.0

    def start(self, dc):
        self._dc = dc

    def ChangeDutyCycle(self, dc):
        self._dc = dc

    def stop(self):
        self._dc = 0.0


def setmode(mode):
    pass


def setwarnings(flag):
    pass


def setup(pin, mode):
    pass


def output(pin, value):
    pass


def input(pin):
    return 0
