# =============================================================================
# AAIQ RELAY BOX PICO 2 W
# -----------------------------------------------------------------------------
# File        : test_relay_sequential.py
# Purpose     : Test sequential relay pulse handling
# Platform    : Raspberry Pi Pico 2 W / RP2350
# Firmware    : MicroPython 1.29.0
# Project     : AAIQ RELAY BOX PICO
# -----------------------------------------------------------------------------
# Test:
#   Start R1 for 300 ms.
#   While R1 is active, queue R2 for 100 ms.
#   Verify that R2 starts only after R1 has finished.
# =============================================================================

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from main import RelayController
except ImportError:
    from src.main import RelayController


relay = RelayController()

print("AAIQ Relay Box Pico 2 W")
print("Sequential relay test")

print("Initial:", relay.states())

result_1 = relay.pulse(1, 300)
print("R1:", result_1)
print("After R1:", relay.states())

time.sleep_ms(50)

result_2 = relay.pulse(2, 100)
print("R2:", result_2)
print("Waiting:", relay.waiting())
print("During R1:", relay.states())

time.sleep_ms(300)
relay.update()

print("After R1:", relay.states())
print("Active:", relay.active())
print("Waiting:", relay.waiting())

time.sleep_ms(100)
relay.update()

print("Final:", relay.states())

if relay.states()[1] == 0 and relay.states()[2] == 0:
    print("PASS: sequential relay test completed")
else:
    print("FAIL: relay state incorrect")
