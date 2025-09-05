#!/usr/bin/env python3
import time
import math
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 12        # adjust to match your fan ring
LED_PIN = 18          # GPIO18 (PWM pin)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 255  # we'll modulate this
LED_INVERT = False
LED_CHANNEL = 0

# Initialize the LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()


def get_led_status():
    """Read LED status from file, default to UV if missing."""
    try:
        with open("/tmp/led_status", "r") as f:
            return f.read().strip().upper()
    except FileNotFoundError:
        return "UV"


try:
    t = 0
    while True:
        # Check LED status from file each frame
        status = get_led_status()

        # Breathing brightness
        min_brightness = 0.3  # 30% minimum brightness
        brightness = (math.sin(t) + 1) / 2  # 0–1 sine wave
        brightness = min_brightness + (1 - min_brightness) * brightness
        t += 0.05  # breathing cycle speed

        if status == "RED":
            # Red breathing
            color = Color(255, 0, 0)
        else:
            # UV breathing
            color = Color(128, 0, 255)

        strip.setBrightness(int(255 * brightness))

        # Apply colour to all LEDs
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, color)
        strip.show()

        time.sleep(0.03)  # refresh rate ~33 FPS

except KeyboardInterrupt:
    # Graceful exit → turn LEDs off
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
