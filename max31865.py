#!/usr/bin/env python3
# The MIT License (MIT)
# Copyright (c) 2015 Stephen P. Smith

import time
import math
import RPi.GPIO as GPIO


class max31865:
    """Read temperature from a MAX31865 RTD amplifier via bit-banged SPI.

    Supports PT100 sensors with a Callendar-Van Dusen temperature conversion.
    Default pins match the SmartCoffee wiring: CS=4, MISO=9, MOSI=10, CLK=11.
    """

    def __init__(self, csPin=4, misoPin=9, mosiPin=10, clkPin=11):
        self.csPin = csPin
        self.misoPin = misoPin
        self.mosiPin = mosiPin
        self.clkPin = clkPin
        self._setup_gpio()

    def _setup_gpio(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.csPin,   GPIO.OUT)
        GPIO.setup(self.misoPin, GPIO.IN)
        GPIO.setup(self.mosiPin, GPIO.OUT)
        GPIO.setup(self.clkPin,  GPIO.OUT)

        GPIO.output(self.csPin,   GPIO.HIGH)
        GPIO.output(self.clkPin,  GPIO.LOW)
        GPIO.output(self.mosiPin, GPIO.LOW)

    def readTemp(self):
        # Config register 0xA2:
        #   bit7 Vbias=1, bit6 ConvMode=0 (manual), bit5 1-shot=1,
        #   bit4 3-wire=1, bits3-2 fault=00, bit1 fault-clear=1, bit0 50/60Hz=0
        self._write_register(0, 0xA2)
        time.sleep(0.1)  # wait for one-shot conversion (~100 ms)

        regs = self._read_registers(0, 8)

        rtd_msb, rtd_lsb = regs[1], regs[2]
        rtd_adc = ((rtd_msb << 8) | rtd_lsb) >> 1

        status = regs[7]
        if status & 0x80:
            raise FaultError("High threshold / cable open")
        if status & 0x40:
            raise FaultError("Low threshold / cable short")
        if status & 0x04:
            raise FaultError("Overvoltage / undervoltage")

        return self._adc_to_celsius(rtd_adc)

    def _adc_to_celsius(self, rtd_adc):
        R_REF = 434.6   # reference resistor (ohms)
        R0    = 100.0   # PT100 resistance at 0 °C
        a     =  3.9083e-3
        b     = -5.775e-7

        r_rtd = rtd_adc * R_REF / 32768.0

        # Callendar-Van Dusen quadratic (valid for 0–850 °C)
        discriminant = a * a * R0 * R0 - 4 * b * R0 * (R0 - r_rtd)
        temp = (-a * R0 + math.sqrt(discriminant)) / (2 * b * R0)

        if temp < 0:
            # Fall back to linear approximation below 0 °C
            temp = (rtd_adc / 32.0) - 256.0

        return temp

    def _write_register(self, reg, data):
        GPIO.output(self.csPin, GPIO.LOW)
        self._send_byte(0x80 | reg)
        self._send_byte(data)
        GPIO.output(self.csPin, GPIO.HIGH)

    def _read_registers(self, reg_start, count):
        result = []
        GPIO.output(self.csPin, GPIO.LOW)
        self._send_byte(reg_start)
        for _ in range(count):
            result.append(self._recv_byte())
        GPIO.output(self.csPin, GPIO.HIGH)
        return result

    def _send_byte(self, byte):
        for _ in range(8):
            GPIO.output(self.clkPin, GPIO.HIGH)
            GPIO.output(self.mosiPin, GPIO.HIGH if (byte & 0x80) else GPIO.LOW)
            byte <<= 1
            GPIO.output(self.clkPin, GPIO.LOW)

    def _recv_byte(self):
        byte = 0
        for _ in range(8):
            GPIO.output(self.clkPin, GPIO.HIGH)
            byte <<= 1
            if GPIO.input(self.misoPin):
                byte |= 1
            GPIO.output(self.clkPin, GPIO.LOW)
        return byte


class FaultError(Exception):
    pass


if __name__ == "__main__":
    sensor = max31865()
    print(f"{sensor.readTemp():.2f} °C")
