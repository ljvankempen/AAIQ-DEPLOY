# =============================================================================
# AAIQ RELAY BOX PICO 2 W
# -----------------------------------------------------------------------------
# File        : test_relay.py
# Purpose     : Test safe relay initialization
# Platform    : Raspberry Pi Pico 2 W / RP2350
# Firmware    : MicroPython 1.29.0
# Project     : AAIQ RELAY BOX PICO
# -----------------------------------------------------------------------------
# Test:
#   Create the RelayController and verify that all 8 relays initialize LOW.
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from main import RelayController
except ImportError:
    from src.main import RelayController


relay = RelayController()

print("AAIQ Relay Box Pico 2 W")
print("Relay initialization test")
print(relay.states())
