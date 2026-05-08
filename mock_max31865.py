"""Mock MAX31865 temperature sensor with realistic thermal simulation."""

import random
import time


class max31865:
    """Simulated PT100 boiler sensor for development (no hardware needed)."""

    def __init__(self, csPin=4, misoPin=9, mosiPin=10, clkPin=11, **kwargs):
        self._temp = 20.0
        self._heater_power = 0.0   # 0–100 %
        self._last_t = time.time()

    def set_heater_power(self, pct: float):
        """Called by the PID worker after each PWM update to drive thermal model."""
        self._heater_power = max(0.0, min(100.0, pct))

    def readTemp(self) -> float:
        now = time.time()
        dt = min(now - self._last_t, 2.0)
        self._last_t = now

        ambient = 20.0
        heating = (self._heater_power / 100.0) * 1.8   # max ~1.8 °C/s at full power
        cooling = 0.025 * (self._temp - ambient)        # proportional to excess heat

        self._temp += (heating - cooling) * dt
        self._temp = max(15.0, min(130.0, self._temp))
        self._temp += random.gauss(0.0, 0.08)           # sensor noise

        return round(self._temp, 2)
