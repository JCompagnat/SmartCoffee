class PWM:
    def __init__(self, pin, freq):
        print(f"Mock PWM started on pin {pin} at freq {freq}")
    def start(self, val): print(f"PWM start with value {val}")
    def ChangeDutyCycle(self, val): print(f"PWM duty cycle changed to {val}")
    def stop(self): print("PWM stopped")

def setmode(mode): print(f"GPIO mode set: {mode}")
def setup(pin, mode): print(f"GPIO setup on pin {pin} as {mode}")
def output(pin, value): print(f"GPIO output on pin {pin}: {value}")
def BCM(): return 'BCM'
def OUT(): return 'OUT'
