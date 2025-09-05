#!/usr/bin/env python3
import time
import math
import psutil  # pip install psutil
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 12
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 255
LED_INVERT = False
LED_CHANNEL = 0

# Initialize the LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def uv_color(intensity):
    """Generate a UV/indigo color with given intensity (0–1 scale)."""
    r = int(128 * intensity)
    g = 0
    b = int(255 * intensity)
    return Color(r, g, b)

try:
    t = 0
    while True:
        # --- Get CPU load (0–100%) ---
        cpu_load = psutil.cpu_percent(interval=0.1)

        # Map load to breathing speed (idle = slow, busy = fast)
        # e.g. 0.01 (very slow) → 0.20 (very fast)
        speed = 0.01 + (cpu_load / 100.0) * 0.19

        # sine wave brightness, never fully off
        min_brightness = 0.3
        brightness = (math.sin(t) + 1) / 2
        brightness = min_brightness + (1 - min_brightness) * brightness

        color = uv_color(brightness)

        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)

        strip.show()
        time.sleep(0.03)  # update rate
        t += speed         # speed tied to CPU load

except KeyboardInterrupt:
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
