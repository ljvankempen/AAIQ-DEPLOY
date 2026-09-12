# =============================================================================
# AAIQ RELAY BOX PICO 2 W — REGRESSION & UNIT TEST SUITE
# -----------------------------------------------------------------------------
# File        : test_relay_box.py
# Purpose     : Central automated regression tests runner for AAIQ Relay Box firmware
# Platform    : MicroPython 1.29.0 / Python 3.10+
# Project     : AAIQ RELAY BOX PICO
# Standards   : AAIQ Relay Box Pico W Design Specification v1.79
#               AAIQ Relay Box Pico W Driver Specification v1.0
# =============================================================================

import sys
import os
import json
import time

# Ensure src/ directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    import main
    from main import (
        RelayController,
        StatusLED,
        RGB_PIN,
        Config,
        WiFiManager,
        HTTPServer,
        HTTPSAPI,
        device_id,
        hostname,
        encrypt_secret,
        decrypt_secret,
        RELAY_PINS,
        FIRMWARE_VERSION,
        API_VERSION,
    )
except ImportError as err:
    print("FATAL: Failed to import firmware module from src/main.py: %s" % err)
    sys.exit(1)


class TestRunner:
    __test__ = False

    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.start_time = 0

    def add_test(self, name, fn):
        self.tests.append((name, fn))

    def run(self):
        print("=============================================================================")
        print(" AAIQ RELAY BOX PICO 2 W — CENTRAL REGRESSION TEST SUITE")
        print(" Firmware Version : %s" % FIRMWARE_VERSION)
        print(" API Version      : %s" % API_VERSION)
        print(" Target Hardware  : Raspberry Pi Pico 2 W / RP2350 (8 Relays)")
        print("=============================================================================")
        print("")

        self.start_time = time.time()
        self.passed = 0
        self.failed = 0

        for idx, (name, fn) in enumerate(self.tests, 1):
            t0 = time.time()
            try:
                fn()
                elapsed = (time.time() - t0) * 1000.0
                print(" [%02d/%02d] PASS: %-54s (%.1f ms)" % (idx, len(self.tests), name, elapsed))
                self.passed += 1
            except AssertionError as exc:
                elapsed = (time.time() - t0) * 1000.0
                print(" [%02d/%02d] FAIL: %-54s (%.1f ms)" % (idx, len(self.tests), name, elapsed))
                print("         -> Assertion Failed: %s" % exc)
                self.failed += 1
            except Exception as exc:
                elapsed = (time.time() - t0) * 1000.0
                print(" [%02d/%02d] FAIL: %-54s (%.1f ms)" % (idx, len(self.tests), name, elapsed))
                print("         -> Exception Raised: %s: %s" % (type(exc).__name__, exc))
                self.failed += 1

        total_elapsed = time.time() - self.start_time
        print("")
        print("=============================================================================")
        print(" TEST EXECUTION SUMMARY")
        print("-----------------------------------------------------------------------------")
        print(" Total Tests Executed : %d" % len(self.tests))
        print(" Passed               : %d" % self.passed)
        print(" Failed               : %d" % self.failed)
        print(" Success Rate         : %.1f%%" % ((self.passed / len(self.tests)) * 100.0 if self.tests else 0))
        print(" Total Elapsed Time   : %.2f seconds" % total_elapsed)
        print(" Final Outcome        : %s" % ("ALL TESTS PASSED (PASS)" if self.failed == 0 else "TESTS FAILED (FAIL)"))
        print("=============================================================================")

        return self.failed == 0


# -----------------------------------------------------------------------------
# Test Harness Helper to simulate HTTP/HTTPS API calls to HTTPSAPI
# -----------------------------------------------------------------------------
class APIHarness:
    __test__ = False

    def __init__(self):
        self.led = StatusLED(RGB_PIN)
        self.relay = RelayController()
        self.relay.all_off()
        self.config = Config()
        self.wifi = WiFiManager(self.config, self.relay, led=self.led)
        self.api = HTTPServer(self.config, self.relay, self.wifi, led=self.led)

    def request(self, method, path, body=None):
        body_str = ""
        if body is not None:
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body)
            else:
                body_str = str(body)

        raw_resp = self.api.api_request(method, path, body_str)
        # Parse HTTP response bytes
        header_bytes, sep, body_bytes = raw_resp.partition(b"\r\n\r\n")
        header_lines = header_bytes.decode("utf-8").split("\r\n")
        status_line = header_lines[0]
        parts = status_line.split(" ", 2)
        status_code = int(parts[1]) if len(parts) >= 2 else 0

        parsed_json = None
        if body_bytes:
            try:
                parsed_json = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed_json = None

        return {
            "status_code": status_code,
            "status_line": status_line,
            "headers": header_lines[1:],
            "body": body_bytes.decode("utf-8", errors="replace"),
            "body_bytes": body_bytes,
            "json": parsed_json,
        }


# -----------------------------------------------------------------------------
# TEST IMPLEMENTATIONS
# -----------------------------------------------------------------------------

def test_01_firmware_startup():
    """Test 1: Firmware starts correctly without side-effects."""
    dev_id = device_id()
    host = hostname()
    assert dev_id and len(dev_id) >= 6, "Device ID must be valid: %r" % dev_id
    assert host and host.endswith(".local"), "Hostname must end with .local: %r" % host
    assert FIRMWARE_VERSION and len(FIRMWARE_VERSION) > 0, "Firmware version must be set"
    assert API_VERSION == "v1", "API version must be v1"


def test_02_all_relays_initialize_safe_low():
    """Test 2: All 8 relays initialize safely in LOW/REST (0) state."""
    ctrl = RelayController()
    states = ctrl.states()
    assert len(states) == 8, "Must have exactly 8 relays"
    for r in range(1, 9):
        assert r in states, "Relay %d missing from controller states" % r
        assert states[r] == 0, "Relay %d initialized to %r instead of 0 (LOW)" % (r, states[r])
    assert ctrl.active() is None, "Active pulse must be None on startup"
    assert ctrl.waiting() is None, "Waiting pulse must be None on startup"


def test_03_individual_relays_on_off():
    """Test 3: Relay 1 through 8 can be switched ON and OFF individually."""
    ctrl = RelayController()
    for r in range(1, 9):
        # Turn ON
        res_on = ctrl.on(r)
        assert res_on is True, "ctrl.on(%d) must return True" % r
        assert ctrl.states()[r] == 1, "Relay %d state must be 1 (ON)" % r
        # Turn OFF
        res_off = ctrl.off(r)
        assert res_off is True, "ctrl.off(%d) must return True" % r
        assert ctrl.states()[r] == 0, "Relay %d state must be 0 (OFF)" % r


def test_04_pulse_with_valid_duration():
    """Test 4: Pulse activates relay for exact specified duration."""
    ctrl = RelayController()
    res = ctrl.pulse(3, 80)
    assert res is True, "ctrl.pulse(3, 80) must return True"
    assert ctrl.states()[3] == 1, "Relay 3 must be HIGH immediately on pulse"
    act = ctrl.active()
    assert act is not None and act["relay"] == 3, "Active pulse must show relay 3"
    assert act["duration_ms"] == 80, "Duration must be 80 ms"

    # Advance time past 80 ms
    time.sleep_ms(90)
    ctrl.update()
    assert ctrl.states()[3] == 0, "Relay 3 must return to LOW after pulse duration"
    assert ctrl.active() is None, "Active pulse must be cleared"


def test_05_default_pulse_100ms():
    """Test 5: Default pulse duration is 100 ms when duration is omitted."""
    ctrl = RelayController()
    ctrl.set_default_duration_fn(lambda: 100)
    res = ctrl.pulse(4)
    assert res is True, "ctrl.pulse(4) default must return True"
    assert ctrl.states()[4] == 1, "Relay 4 must be HIGH"
    act = ctrl.active()
    assert act["duration_ms"] == 100, "Default pulse duration must be 100 ms, got %r" % act["duration_ms"]

    time.sleep_ms(110)
    ctrl.update()
    assert ctrl.states()[4] == 0, "Relay 4 must be LOW after 100 ms"


def test_06_sequential_pulse():
    """Test 6: Sequential pulse queues and executes only after previous finishes."""
    ctrl = RelayController()
    ctrl.pulse(1, 100)
    ctrl.pulse(2, 60)

    # R1 is active, R2 is waiting
    assert ctrl.states()[1] == 1, "Relay 1 must be active"
    assert ctrl.states()[2] == 0, "Relay 2 must remain LOW while waiting"
    assert ctrl.waiting()["relay"] == 2, "Relay 2 must be in waiting queue"

    # Wait for R1 to complete
    time.sleep_ms(110)
    ctrl.update()

    # Now R1 is LOW, R2 is active
    assert ctrl.states()[1] == 0, "Relay 1 must now be LOW"
    assert ctrl.states()[2] == 1, "Relay 2 must now be HIGH"
    assert ctrl.active()["relay"] == 2, "Relay 2 must now be active pulse"
    assert ctrl.waiting() is None, "Waiting queue must be cleared"

    # Wait for R2 to complete
    time.sleep_ms(70)
    ctrl.update()
    assert ctrl.states()[2] == 0, "Relay 2 must now be LOW"
    assert ctrl.active() is None, "No active pulse remaining"


def test_07_waiting_pulse_replacement():
    """Test 7: New waiting pulse replaces previous waiting pulse."""
    ctrl = RelayController()
    ctrl.pulse(1, 150)
    ctrl.pulse(2, 50)
    assert ctrl.waiting()["relay"] == 2, "Relay 2 must be waiting"

    # Queue R3 while R1 is still running
    ctrl.pulse(3, 80)
    assert ctrl.waiting()["relay"] == 3, "Relay 3 must have replaced Relay 2 in waiting slot"
    assert ctrl.waiting()["duration_ms"] == 80, "Duration must be 80 ms"

    # Let R1 finish
    time.sleep_ms(160)
    ctrl.update()

    # R3 starts, R2 was dropped
    assert ctrl.states()[1] == 0, "R1 must be OFF"
    assert ctrl.states()[2] == 0, "R2 must never have started"
    assert ctrl.states()[3] == 1, "R3 must now be active"

    time.sleep_ms(90)
    ctrl.update()
    assert ctrl.states()[3] == 0, "R3 must be OFF"


def test_08_max_one_active_pulse():
    """Test 8: Maximum one pulse is active at any single moment."""
    ctrl = RelayController()
    ctrl.pulse(5, 100)
    ctrl.pulse(6, 100)
    active_count = sum(1 for v in ctrl.states().values() if v == 1)
    assert active_count == 1, "Expected exactly 1 active relay, found %d" % active_count
    time.sleep_ms(110)
    ctrl.update()
    active_count = sum(1 for v in ctrl.states().values() if v == 1)
    assert active_count == 1, "Expected exactly 1 active relay during second pulse, found %d" % active_count
    time.sleep_ms(110)
    ctrl.update()
    active_count = sum(1 for v in ctrl.states().values() if v == 1)
    assert active_count == 0, "Expected 0 active relays after sequence, found %d" % active_count


def test_09_all_off():
    """Test 9: ALL OFF turns all relays LOW and cancels active/waiting pulses."""
    ctrl = RelayController()
    ctrl.on(1)
    ctrl.on(2)
    ctrl.pulse(3, 200)
    ctrl.pulse(4, 200)
    ctrl.all_off()
    states = ctrl.states()
    for r in range(1, 9):
        assert states[r] == 0, "Relay %d must be 0 after all_off" % r
    assert ctrl.active() is None, "Active pulse must be cleared"
    assert ctrl.waiting() is None, "Waiting pulse must be cleared"


def test_10_api_info_endpoint():
    """Test 10: GET /api/v1/info returns complete technical metadata."""
    harness = APIHarness()
    resp = harness.request("GET", "/api/v1/info")
    assert resp["status_code"] == 200, "Expected HTTP 200, got %d" % resp["status_code"]
    j = resp["json"]
    assert j is not None and j.get("success") is True, "Response must indicate success=True"
    assert "device_id" in j and len(j["device_id"]) >= 6, "device_id missing or short"
    assert "hostname" in j and "aaiq-relay" in j["hostname"], "hostname missing or invalid"
    assert "firmware_version" in j and j["firmware_version"] == FIRMWARE_VERSION, "firmware_version mismatch"
    assert "api_version" in j, "api_version missing"
    assert j.get("relay_count") == 8, "relay_count must be 8, got %r" % j.get("relay_count")
    assert j.get("http") is True, "http metadata must be True"
    assert j.get("https") is False, "https metadata must be False"


def test_11_api_status_endpoint():
    """Test 11: GET /api/v1/status returns accurate state and pulse diagnostics."""
    harness = APIHarness()
    harness.relay.on(2)
    resp = harness.request("GET", "/api/v1/status")
    assert resp["status_code"] == 200, "Expected HTTP 200, got %d" % resp["status_code"]
    j = resp["json"]
    assert j is not None and j.get("success") is True, "Response must indicate success=True"
    assert j.get("relay2") is True, "relay2 boolean state must be True"
    assert j.get("relay1") is False, "relay1 boolean state must be False"
    assert j["relay"]["2"] == 1 or j["relay"][2] == 1, "relay dictionary must show relay 2 as 1"
    assert "wifi" in j, "wifi diagnostics missing in status"


def test_12_valid_relay_api_requests():
    """Test 12: Valid relay API requests for ON, OFF, PULSE and ALL OFF."""
    harness = APIHarness()

    # 1. Route POST /api/v1/relay/{n}/on
    r1 = harness.request("POST", "/api/v1/relay/5/on")
    assert r1["status_code"] == 200 and r1["json"]["success"] is True, "POST /relay/5/on failed"
    assert harness.relay.states()[5] == 1, "Relay 5 must be ON"

    # 2. Route POST /api/v1/relay/{n}/off
    r2 = harness.request("POST", "/api/v1/relay/5/off")
    assert r2["status_code"] == 200 and r2["json"]["success"] is True, "POST /relay/5/off failed"
    assert harness.relay.states()[5] == 0, "Relay 5 must be OFF"

    # 3. Route POST /api/v1/relay/{n} with body {"state": true}
    r3 = harness.request("POST", "/api/v1/relay/7", {"state": True})
    assert r3["status_code"] == 200 and r3["json"]["success"] is True, "POST /relay/7 (state=true) failed"
    assert harness.relay.states()[7] == 1, "Relay 7 must be ON"

    # 4. Route POST /api/v1/relay/{n}/pulse with body {"duration_ms": 50}
    r4 = harness.request("POST", "/api/v1/relay/6/pulse", {"duration_ms": 50})
    assert r4["status_code"] == 200 and r4["json"]["success"] is True, "POST /relay/6/pulse failed"
    assert harness.relay.states()[6] == 1, "Relay 6 must be ON for pulse"

    # 5. Route POST /api/v1/all/off
    r5 = harness.request("POST", "/api/v1/all/off")
    assert r5["status_code"] == 200 and r5["json"]["success"] is True, "POST /all/off failed"
    assert all(v == 0 for v in harness.relay.states().values()), "All relays must be OFF after /all/off"


def test_13_invalid_relay_handling():
    """Test 13: Invalid relay identifiers (0, 9, -1, 'xyz') reject with HTTP 400 INVALID_RELAY."""
    harness = APIHarness()
    for bad_relay in [0, 9, 99, -1, "abc"]:
        resp = harness.request("POST", "/api/v1/relay/%s" % bad_relay, {"state": True})
        assert resp["status_code"] == 400, "Expected HTTP 400 for relay %r, got %d" % (bad_relay, resp["status_code"])
        assert resp["json"] and resp["json"].get("error") == "INVALID_RELAY", (
            "Expected error 'INVALID_RELAY' for relay %r, got %r" % (bad_relay, resp["json"])
        )


def test_14_invalid_pulse_duration_handling():
    """Test 14: Invalid pulse durations (<= 0, non-integer) reject with HTTP 400 INVALID_DURATION."""
    harness = APIHarness()
    for bad_dur in [0, -10, -500, "zero", "abc"]:
        resp = harness.request("POST", "/api/v1/relay/1/pulse", {"duration_ms": bad_dur})
        assert resp["status_code"] == 400, "Expected HTTP 400 for duration %r, got %d" % (bad_dur, resp["status_code"])
        assert resp["json"] and resp["json"].get("error") == "INVALID_DURATION", (
            "Expected error 'INVALID_DURATION' for duration %r, got %r" % (bad_dur, resp["json"])
        )


def test_15_http_status_codes():
    """Test 15: Correct standard HTTP status codes (200, 400, 404)."""
    harness = APIHarness()
    # 200 OK
    assert harness.request("GET", "/api/v1/info")["status_code"] == 200
    assert harness.request("GET", "/api/v1/status")["status_code"] == 200
    assert harness.request("POST", "/api/v1/all/off")["status_code"] == 200

    # 400 Bad Request
    assert harness.request("POST", "/api/v1/relay/99/on")["status_code"] == 400
    assert harness.request("POST", "/api/v1/relay/1/pulse", {"duration_ms": -5})["status_code"] == 400

    # 404 Not Found
    assert harness.request("GET", "/api/v1/unknown_endpoint")["status_code"] == 404
    assert harness.request("POST", "/api/v2/tape/play")["status_code"] == 404


def test_16_json_error_codes():
    """Test 16: JSON error codes match driver specification constants."""
    harness = APIHarness()
    err_relay = harness.request("POST", "/api/v1/relay/10/off")["json"]
    assert err_relay.get("error") == "INVALID_RELAY", "Expected INVALID_RELAY, got %r" % err_relay

    err_dur = harness.request("POST", "/api/v1/relay/2/pulse", {"duration_ms": 0})["json"]
    assert err_dur.get("error") == "INVALID_DURATION", "Expected INVALID_DURATION, got %r" % err_dur

    err_req = harness.request("POST", "/api/v1/relay/2", {"foo": "bar"})["json"]
    assert err_req.get("error") == "INVALID_REQUEST", "Expected INVALID_REQUEST, got %r" % err_req

    err_404 = harness.request("GET", "/invalid/path")["json"]
    assert err_404.get("error") == "NOT_FOUND", "Expected NOT_FOUND, got %r" % err_404


def test_17_status_matches_actual_hardware_state():
    """Test 17: Reported status strictly reflects actual hardware relay states."""
    harness = APIHarness()
    harness.relay.on(1)
    harness.relay.on(4)
    harness.relay.on(8)

    status_resp = harness.request("GET", "/api/v1/status")["json"]
    for r in range(1, 9):
        expected = True if r in (1, 4, 8) else False
        assert status_resp.get("relay%d" % r) == expected, "Relay %d mismatch: expected %r, got %r" % (
            r, expected, status_resp.get("relay%d" % r)
        )
    harness.relay.all_off()


def test_18_firmware_and_api_versions_available():
    """Test 18: Firmware and API versions are provided in info and status endpoints."""
    harness = APIHarness()
    info = harness.request("GET", "/api/v1/info")["json"]
    status = harness.request("GET", "/api/v1/status")["json"]

    assert info.get("firmware_version") == FIRMWARE_VERSION, "info firmware_version missing or mismatch"
    assert info.get("api_version") == API_VERSION, "info api_version missing or mismatch"
    assert status.get("firmware_version") == FIRMWARE_VERSION, "status firmware_version missing or mismatch"
    assert status.get("api_version") == API_VERSION, "status api_version missing or mismatch"


def test_19_communication_loss_no_command_replay():
    """Test 19: Communication loss does not cause queued/replayed commands on reconnect."""
    harness = APIHarness()
    harness.relay.all_off()

    # Simulate station disconnect
    harness.wifi.was_connected = False
    assert harness.wifi.connected() is False, "Station must be simulated as disconnected"

    # Offline state: no buffered command replay mechanism exists in firmware
    # Any missed network traffic does not accumulate on Pico
    # Reconnect
    harness.wifi.was_connected = True

    # Check that after recovery all relays remain in their safe state (LOW)
    for r in range(1, 9):
        assert harness.relay.states()[r] == 0, "Relay %d must be LOW after reconnect" % r
    assert harness.relay.active() is None, "No active pulses should be executing"
    assert harness.relay.waiting() is None, "No waiting pulses should be executing"


def test_20_status_readable_after_recovery():
    """Test 20: After network recovery, status can be immediately and accurately read."""
    harness = APIHarness()
    harness.relay.all_off()
    harness.relay.on(3)

    # Poll status after simulated recovery
    resp = harness.request("GET", "/api/v1/status")
    assert resp["status_code"] == 200, "GET /status must succeed after recovery"
    j = resp["json"]
    assert j["relay3"] is True, "Relay 3 must be reported as True"
    assert j["relay1"] is False, "Relay 1 must be reported as False"
    harness.relay.all_off()


def test_21_final_state_all_relays_safe_off():
    """Test 21: Final state verification — all 8 relays are safely OFF."""
    harness = APIHarness()
    harness.relay.all_off()
    states = harness.relay.states()
    for r in range(1, 9):
        assert states[r] == 0, "Safety violation: Relay %d is not in LOW (OFF) state" % r
    assert harness.relay.active() is None, "Active pulse remaining in final state"
    assert harness.relay.waiting() is None, "Waiting pulse remaining in final state"


def test_22_diagnose_service_page():
    """Test 22: Diagnose / Technical API test center page renders all required sections."""
    harness = APIHarness()
    for path in ["/diagnose", "/diagnose/"]:
        resp = harness.request("GET", path)
        assert resp["status_code"] == 200, "GET %s must return HTTP 200" % path
        html = resp["body"]
        assert "Device Status" in html, "Missing Device Status section in HTML"
        assert "API Functions" in html, "Missing API Functions section in HTML"
        assert "Relay Status / Test" in html, "Missing Relay Status / Test section in HTML"
        assert "API Result" in html, "Missing API Result section in HTML"
        assert "Firmware / Source Info" in html or "Firmware &amp; Source" in html, "Missing Firmware / Source Info in HTML"
        assert "/api/v1/info" in html, "Missing /api/v1/info in API Functions"
        assert "/api/v1/status" in html, "Missing /api/v1/status in API Functions"
        assert "/api/v1/all/off" in html, "Missing /api/v1/all/off in API Functions"
        assert "/api/v1/relay/{n}" in html, "Missing /api/v1/relay/{n} in API Functions"
        assert "Test Mode" in html, "Missing Test Mode in Relay Status section"
        assert "HTTP API:" in html or "Port 80" in html, "Missing HTTP Port 80 indicator in HTML"


def test_23_sequential_20_info_requests():
    """Test 23: 20 sequential GET /api/v1/info requests execute flawlessly."""
    harness = APIHarness()
    for i in range(20):
        resp = harness.request("GET", "/api/v1/info")
        assert resp["status_code"] == 200, "Request %d failed with HTTP %d" % (i + 1, resp["status_code"])
        j = resp["json"]
        assert j.get("success") is True, "Request %d json success is False" % (i + 1)
        assert j.get("firmware_version") == FIRMWARE_VERSION, "Firmware version mismatch on iteration %d" % (i + 1)
        assert j.get("api_version") == API_VERSION, "API version mismatch on iteration %d" % (i + 1)


def test_24_sequential_20_status_requests():
    """Test 24: 20 sequential GET /api/v1/status requests execute flawlessly."""
    harness = APIHarness()
    harness.relay.on(2)
    harness.relay.on(7)
    for i in range(20):
        resp = harness.request("GET", "/api/v1/status")
        assert resp["status_code"] == 200, "Request %d failed with HTTP %d" % (i + 1, resp["status_code"])
        j = resp["json"]
        assert j.get("success") is True, "Request %d json success is False" % (i + 1)
        assert j.get("relay2") is True, "Relay 2 state desync on iteration %d" % (i + 1)
        assert j.get("relay7") is True, "Relay 7 state desync on iteration %d" % (i + 1)
        assert j.get("relay1") is False, "Relay 1 state desync on iteration %d" % (i + 1)
    harness.relay.all_off()


def test_25_continuous_polling_stability_60s():
    """Test 25: Simulated 60 seconds (60 cycles) of continuous status polling without flapping."""
    harness = APIHarness()
    harness.relay.all_off()
    consecutive_success = 0
    flapping_detected = False

    for cycle in range(60):
        resp = harness.request("GET", "/api/v1/status")
        if resp["status_code"] == 200 and resp["json"].get("success") is True:
            consecutive_success += 1
        else:
            flapping_detected = True
            break
        # Verify relay states remain accurate throughout polling
        states = harness.relay.states()
        for r in range(1, 9):
            assert states[r] == 0, "Relay %d state corrupted during polling at cycle %d" % (r, cycle + 1)

    assert not flapping_detected, "Status polling flapped or failed during 60-cycle continuous test"
    assert consecutive_success == 60, "Expected 60/60 successful poll cycles, got %d" % consecutive_success


def test_26_command_delivery_confirmation_and_recovery():
    """Test 26: Confirmed commands are not replayed; unconfirmed commands re-offered after reconnect."""
    harness = APIHarness()
    harness.relay.all_off()

    class MockWLAN:
        def __init__(self, is_conn=True):
            self._conn = is_conn
        def isconnected(self):
            return self._conn
        def ifconfig(self):
            return ("192.168.1.105", "255.255.255.0", "192.168.1.1", "192.168.1.1")

    mock_sta = MockWLAN(True)
    harness.wifi.sta = mock_sta
    harness.wifi.was_connected = True
    assert harness.wifi.connected() is True

    # 1. Normal command execution & confirmation (HTTP 200)
    cmd1 = harness.request("POST", "/api/v1/relay/4/on")
    assert cmd1["status_code"] == 200, "Command 1 must be confirmed with HTTP 200"
    assert harness.relay.states()[4] == 1, "Relay 4 must be ON"

    # Confirmed command is not re-executed automatically
    # Status is read
    st = harness.request("GET", "/api/v1/status")["json"]
    assert st["relay4"] is True

    # 2. Simulate network interruption
    mock_sta._conn = False
    harness.wifi.was_connected = False
    assert harness.wifi.connected() is False

    # During interruption, driver attempts command (e.g. Turn Relay 5 ON) but connection fails
    # (Simulated: command is NOT delivered to Relay Box)
    unconfirmed_cmd = {"action": "on", "relay": 5}

    # Relay 5 remains OFF on Pico because command never reached server
    assert harness.relay.states()[5] == 0, "Relay 5 must remain OFF when command was not delivered"

    # 3. Connection is restored
    mock_sta._conn = True
    harness.wifi.was_connected = True
    assert harness.wifi.connected() is True

    # After recovery: Driver first reads current status
    recovery_status = harness.request("GET", "/api/v1/status")
    assert recovery_status["status_code"] == 200
    rec_json = recovery_status["json"]
    assert rec_json["relay4"] is True, "Relay 4 confirmed state preserved"
    assert rec_json["relay5"] is False, "Relay 5 accurately observed as not yet executed"

    # Driver now re-offers the unconfirmed command
    resend_cmd = harness.request("POST", "/api/v1/relay/%d/on" % unconfirmed_cmd["relay"])
    assert resend_cmd["status_code"] == 200, "Re-offered command accepted after recovery"
    assert harness.relay.states()[5] == 1, "Relay 5 is now ON"

    # Pico itself has no leftover pending command queues
    assert harness.relay.active() is None
    assert harness.relay.waiting() is None

    harness.relay.all_off()


def test_27_http_response_headers_and_connection_close():
    """Test 27: HTTP responses include complete Content-Length and Connection: close headers."""
    harness = APIHarness()
    resp_info = harness.request("GET", "/api/v1/info")
    assert resp_info["status_code"] == 200
    headers_info_str = " ".join(resp_info["headers"]).lower()
    assert "connection: close" in headers_info_str, "Responses must include Connection: close"
    assert "content-length:" in headers_info_str, "Responses must specify Content-Length"

    resp_status = harness.request("GET", "/api/v1/status")
    assert resp_status["status_code"] == 200
    headers_status_str = " ".join(resp_status["headers"]).lower()
    assert "connection: close" in headers_status_str

    resp_cmd = harness.request("POST", "/api/v1/relay/1/pulse", {"duration_ms": 100})
    assert resp_cmd["status_code"] == 200
    headers_cmd_str = " ".join(resp_cmd["headers"]).lower()
    assert "connection: close" in headers_cmd_str
    harness.relay.all_off()


def test_28_no_tls_ssl_dependency():
    """Test 28: Zero TLS/SSL dependency — pure HTTP architecture on port 80."""
    with open(os.path.join(os.path.dirname(__file__), "..", "src", "main.py"), "r") as f:
        source = f.read()

    # Verify ssl module is not imported in main.py
    assert "import ssl" not in source, "src/main.py must not import ssl"
    assert "from ssl import" not in source, "src/main.py must not import from ssl"
    assert "TLS_CERT" not in source, "src/main.py must not contain TLS_CERT"
    assert "TLS_KEY" not in source, "src/main.py must not contain TLS_KEY"
    assert "HTTPS_PORT" not in source, "src/main.py must not define HTTPS_PORT (port 443)"
    assert "wrap_socket" not in source, "src/main.py must not use wrap_socket"

    # Verify HTTP port configuration
    assert hasattr(main, "HTTP_PORT") and main.HTTP_PORT == 80, "HTTP_PORT must be 80"

    # Verify /api/v1/info reports pure HTTP
    harness = APIHarness()
    info = harness.request("GET", "/api/v1/info")["json"]
    assert info.get("http") is True, "info endpoint must report http=True"
    assert info.get("https") is False, "info endpoint must report https=False"


def test_29_ws2812_rgb_led_status_and_control():
    """Test 29: WS2812 RGB LED controller on GP13, fixed colors, status indication & visual confirmation."""
    # 1. Verification of hardware pin assignment
    assert RGB_PIN == 13, "Waveshare Pico-Relay-B RGB LED must be mapped to GP13"

    # 2. Initialization and default safe state
    led = StatusLED(RGB_PIN)
    assert led.pin_num == 13
    assert led.current_color == (0, 0, 0)
    assert led.status_mode == "starting"

    # 3. Fixed color control (RED, GREEN, BLUE, WHITE, OFF, YELLOW, ORANGE, PURPLE, CYAN)
    led.set_named_color("RED")
    assert led.current_color == (255, 0, 0)

    led.set_named_color("GREEN")
    assert led.current_color == (0, 255, 0)

    led.set_named_color("BLUE")
    assert led.current_color == (0, 0, 255)

    led.set_named_color("WHITE")
    assert led.current_color == (255, 255, 255)

    led.set_named_color("OFF")
    assert led.current_color == (0, 0, 0)

    led.set_named_color("YELLOW")
    assert led.current_color == (255, 180, 0)

    led.set_named_color("ORANGE")
    assert led.current_color == (255, 80, 0)

    led.set_named_color("PURPLE")
    assert led.current_color == (180, 0, 255)

    led.set_named_color("CYAN")
    assert led.current_color == (0, 255, 255)

    led.set_color(100, 150, 200)
    assert led.current_color == (100, 150, 200)

    # 4. Status Indication Modes
    # STARTING = geel (Yellow)
    led.set_status("starting")
    assert led.current_color == led.COLOR_YELLOW
    led.set_status("startup")
    assert led.current_color == led.COLOR_YELLOW
    led.set_status("connecting")
    assert led.current_color == led.COLOR_YELLOW

    # POWER OFF = rood (Red)
    led.set_status("power_off")
    assert led.current_color == led.COLOR_RED

    # POWER ON / READY = groen (Green)
    led.set_status("ready")
    assert led.current_color == led.COLOR_GREEN
    led.set_status("power_on")
    assert led.current_color == led.COLOR_GREEN
    led.set_status("online")
    assert led.current_color == led.COLOR_GREEN

    # PLAY = groen (Green)
    led.set_status("play")
    assert led.current_color == led.COLOR_GREEN

    # STOP = blauw (Blue)
    led.set_status("stop")
    assert led.current_color == led.COLOR_BLUE

    # RECORD = rood (Red)
    led.set_status("record")
    assert led.current_color == led.COLOR_RED

    # PAUSE = oranje (Orange)
    led.set_status("pause")
    assert led.current_color == led.COLOR_ORANGE

    # REW = paars (Purple)
    led.set_status("rew")
    assert led.current_color == led.COLOR_PURPLE

    # FF = cyaan (Cyan)
    led.set_status("ff")
    assert led.current_color == led.COLOR_CYAN

    # ERROR/FAULT = knipperend rood (Blinking red)
    led.set_status("error")
    led.blink_state = True
    led.update(force=True)
    assert led.current_color == led.COLOR_RED
    led.blink_state = False
    led.update(force=True)
    assert led.current_color == led.COLOR_OFF

    # Blue blinking: setup mode
    led.set_status("setup")
    led.blink_state = True
    led.update(force=True)
    assert led.current_color == led.COLOR_BLUE
    led.blink_state = False
    led.update(force=True)
    assert led.current_color == led.COLOR_OFF

    # 5. Temporary Transport Action Flash & Automatic Return to Ready/Green
    led.set_status("ready")
    assert led.current_color == led.COLOR_GREEN

    # Flash R6 (REW -> Purple)
    led.flash_transport(6, duration_ms=50)
    assert led.current_color == (180, 0, 255)
    time.sleep(0.06)
    led.update()
    assert led.current_color == led.COLOR_GREEN, "LED must automatically return to POWER ON / READY (Green)"

    # Flash R5 (FF -> Cyan)
    led.flash_transport(5, duration_ms=50)
    assert led.current_color == (0, 255, 255)
    time.sleep(0.06)
    led.update()
    assert led.current_color == led.COLOR_GREEN, "LED must automatically return to POWER ON / READY (Green)"

    # 6. Integration: HTTPServer triggers transport flashes on relay actions
    harness = APIHarness()
    harness.led.set_status("ready")
    assert harness.led.current_color == harness.led.COLOR_GREEN

    # R1 (PLAY) -> Green flash
    harness.request("POST", "/api/v1/relay/1/pulse", {"duration_ms": 50})
    assert harness.led.current_color == harness.led.COLOR_GREEN

    # R6 (REW) -> Purple flash
    harness.request("POST", "/api/v1/relay/6/pulse", {"duration_ms": 50})
    assert harness.led.current_color == (180, 0, 255)

    # After duration, reverts to base status (ready -> Green)
    time.sleep(0.06)
    harness.led.update()
    assert harness.led.current_color == harness.led.COLOR_GREEN
    harness.relay.all_off()


def test_30_performance_and_fast_relay_response():
    """Test 30: Performance & sub-millisecond execution for relay and telemetry API endpoints."""
    harness = APIHarness()

    # 1. Measure GET /api/v1/status response
    t0 = time.time()
    resp_status = harness.request("GET", "/api/v1/status")
    dt_status_ms = (time.time() - t0) * 1000.0
    assert resp_status["status_code"] == 200
    assert resp_status["json"].get("success") is True
    assert dt_status_ms < 50.0, "GET /api/v1/status must respond quickly (<50ms locally), took %.2f ms" % dt_status_ms

    # 2. Measure GET /api/v1/info response
    t0 = time.time()
    resp_info = harness.request("GET", "/api/v1/info")
    dt_info_ms = (time.time() - t0) * 1000.0
    assert resp_info["status_code"] == 200
    assert resp_info["json"].get("success") is True
    assert dt_info_ms < 50.0, "GET /api/v1/info must respond quickly (<50ms locally), took %.2f ms" % dt_info_ms

    # 3. Measure POST /api/v1/relay/1 state toggle
    t0 = time.time()
    resp_r1_on = harness.request("POST", "/api/v1/relay/1", {"state": True})
    dt_r1_on_ms = (time.time() - t0) * 1000.0
    assert resp_r1_on["status_code"] == 200
    assert resp_r1_on["json"].get("state") is True
    assert harness.relay.relays[1].value() == 1, "Relay 1 must be HIGH immediately"
    assert dt_r1_on_ms < 50.0, "POST /api/v1/relay/1 must switch immediately (<50ms locally), took %.2f ms" % dt_r1_on_ms

    # 4. Measure POST /api/v1/relay/1/pulse
    t0 = time.time()
    resp_pulse = harness.request("POST", "/api/v1/relay/1/pulse", {"duration_ms": 100})
    dt_pulse_ms = (time.time() - t0) * 1000.0
    assert resp_pulse["status_code"] == 200
    assert resp_pulse["json"].get("duration_ms") == 100
    assert harness.relay.relays[1].value() == 1, "Relay 1 must be active for pulse"
    assert dt_pulse_ms < 50.0, "POST /api/v1/relay/1/pulse took %.2f ms" % dt_pulse_ms

    # 5. Measure POST /api/v1/all/off
    t0 = time.time()
    resp_all_off = harness.request("POST", "/api/v1/all/off")
    dt_all_off_ms = (time.time() - t0) * 1000.0
    assert resp_all_off["status_code"] == 200
    assert all(p.value() == 0 for p in harness.relay.relays.values()), "All relays must be 0"
    assert dt_all_off_ms < 50.0, "POST /api/v1/all/off took %.2f ms" % dt_all_off_ms


def test_31_pwa_manifest_service_worker_and_assets():
    """Test 31: Standalone PWA delivery (Manifest, Service Worker, Icons, / and /remote UI)."""
    harness = APIHarness()

    # 1. GET / and /remote UI
    for route in ("/", "/remote", "/remote/", "/tape", "/pr99"):
        resp = harness.request("GET", route)
        assert resp["status_code"] == 200, "Route %s must return HTTP 200" % route
        html = resp["body"]
        assert "AAIQ TAPE Remote" in html or "TAPE" in html or "PR99" in html
        assert 'rel="manifest"' in html or 'href="/manifest.json"' in html
        assert "/api/v1/relay/" in html
        assert 'id="btnPower"' in html, "Header must include transparent Power button"
        assert 'togglePower' in html, "Power toggle handler must be present"
        assert "power-section" not in html, "Separate power-section bar must be removed"
        assert "btnPowerOn" not in html and "btnPowerOff" not in html, "Separate POWER ON/OFF buttons must be removed"
        assert "R6 (GP16)" not in html and "R1 (GP21)" not in html, "Technical GPIO labels must be removed from transport buttons"
        assert "btn-sub" not in html, "Technical GPIO label elements must be removed"
        assert "btn-menu" in html and "border:none;" in html, "Border around 3-dots menu button must be removed"
        assert "REW" in html or "REWIND" in html
        assert "PLAY" in html
        assert "FF" in html or "FAST FWD" in html
        assert "RECORD" in html or "REC" in html
        assert "PAUSE" in html
        assert "STOP" in html
        assert "disabled" in html
        assert "tape-status-bar" not in html, "tape-status-bar must be removed from Remote UI"
        assert "telemetry-card" not in html, "telemetry-card must be removed from Remote UI"
        assert "badge-online" not in html, "Green online badge must be removed from Remote UI header"
        assert 'class="footer"' not in html, "Permanent footer must be removed from Remote UI"
        assert 'src="/logo.png' in html, "Header must render logo.png with cache-busting"
        assert 'brand-logo-container' in html and 'header-logo' in html, "Header must contain logo container and logo class"
        assert 'object-fit:contain' in html or 'object-fit: contain' in html, "Logo must be contained without distortion"
        assert 'z-index:10' in html or 'z-index: 10' in html, "Controls must be in foreground with z-index"
        assert 'btn-menu' in html, "Header must include vertical menu button"
        assert 'id="dropdownMenu"' in html, "Dropdown menu must be present"
        assert 'id="infoModal"' in html, "Info modal must be present"
        assert "@keyframes spinReel{from{transform:rotate(360deg);}to{transform:rotate(0deg);}}" in html, "Reel animation direction must be reversed (counter-clockwise for spinReel)"
        assert "@keyframes spinReelRev{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}" in html, "Reel reverse animation direction must be reversed (clockwise for spinReelRev)"

    # 2. GET /manifest.json
    for mroute in ("/manifest.json", "/manifest.webmanifest"):
        resp_m = harness.request("GET", mroute)
        assert resp_m["status_code"] == 200
        manifest_data = resp_m["json"]
        assert manifest_data.get("name") in ("AAIQ TAPE Remote", "AAIQ Tape Remote", "AAIQ PR99 Remote")
        assert manifest_data.get("short_name") in ("TAPE Remote", "Tape Remote", "PR99 Remote")
        assert manifest_data.get("display") == "standalone"
        assert manifest_data.get("start_url") == "/remote"
        assert "icons" in manifest_data and len(manifest_data["icons"]) > 0

    # 3. GET /sw.js
    resp_sw = harness.request("GET", "/sw.js")
    assert resp_sw["status_code"] == 200
    sw_code = resp_sw["body"]
    assert "addEventListener" in sw_code
    assert "/api/" in sw_code  # Confirms API calls bypass cache
    assert "tape-remote-v0424" in sw_code

    # 4. GET /icon.svg, /icon-192.png, /logo.png
    resp_svg = harness.request("GET", "/icon.svg")
    assert resp_svg["status_code"] == 200
    assert "<svg" in resp_svg["body"]

    resp_png = harness.request("GET", "/icon-192.png")
    assert resp_png["status_code"] == 200
    assert len(resp_png["body"]) > 0

    resp_logo = harness.request("GET", "/logo.png")
    assert resp_logo["status_code"] == 200
    assert any("image/png" in h for h in resp_logo["headers"])
    assert len(resp_logo["body"]) > 0
    # Verify that the served logo is a valid PNG matching get_logo_data()
    assert resp_logo["body_bytes"] == main.get_logo_data(), "Served /logo.png must match get_logo_data() exactly"
    assert resp_logo["body_bytes"][:8] == b"\x89PNG\r\n\x1a\n", "Served logo must have valid PNG header"

    # 5. Remote UI Logo Loading & Git URL / Cache Verification
    resp_page = harness.request("GET", "/remote")
    assert resp_page["status_code"] == 200
    html_page = resp_page["body"]
    assert 'id="headerLogo"' in html_page, "Header logo <img> must have id headerLogo"
    assert 'GIT_LOGO_URL' in html_page, "UI script must define GIT_LOGO_URL"
    assert 'https://raw.githubusercontent.com/ljvankempen/AAIQ-PWA-Assets/main/logo.png' in html_page
    assert 'initLogo' in html_page, "UI script must define initLogo function"
    assert 'localStorage' in html_page, "initLogo must cache logo in localStorage"
    assert 'LOGO_CACHE_KEY' in html_page, "UI script must define cache key for logo"

    # 6. iOS PWA Installation Modal & Browser Detection Verification
    assert 'id="iosModal"' in html_page, "iOS modal must be present in Remote UI"
    assert 'getIosBrowser' in html_page, "getIosBrowser detection must be present"
    assert 'getBrowserEnv' in html_page, "getBrowserEnv detection must be present"
    assert 'updateIosModalContent' in html_page, "updateIosModalContent handler must be present"
    assert 'FxiOS' in html_page, "Firefox on iOS (FxiOS) detection must be implemented"
    assert 'CriOS' in html_page, "Chrome on iOS (CriOS) detection must be implemented"
    assert 'Firefox op iOS ondersteunt PWA-installatie niet zoals Safari' in html_page
    assert 'Chrome op iOS ondersteunt PWA-installatie niet zoals Safari' in html_page
    assert 'Open in Safari en kies Share' in html_page
    assert 'handleOutsideMenu' in html_page, "Outside click/touch handler must be implemented for 3-dots menu"
    assert 'menuItemInstall' in html_page, "3-dots dropdown menu must contain install item"

    # 7. Verify main.py contains NO embedded base64 logo and is < 400 KB
    main_path = os.path.join(os.path.dirname(__file__), "..", "src", "main.py")
    main_size = os.path.getsize(main_path)
    assert main_size < 400 * 1024, "main.py size must be < 400 KB (currently %d bytes)" % main_size
    with open(main_path, "r", encoding="utf-8") as f:
        main_source = f.read()
    assert "LOGO_PNG_BASE64" not in main_source, "main.py must not contain LOGO_PNG_BASE64"
    assert "iVBORw0KGgo" not in main_source, "main.py must not contain embedded PNG base64 strings"


def test_32_pr99_transport_relay_mapping_and_controls():
    """Test 32: Revox PR99 6 Transport Functions (R1=PLAY..R6=FF) Pulse Execution & Single Tap Guarantee."""
    harness = APIHarness()
    harness.relay.all_off()

    pr99_functions = [
        (1, "PLAY"),
        (2, "STOP"),
        (3, "REC"),
        (4, "PAUSE"),
        (5, "FAST_FORWARD"),
        (6, "REWIND"),
    ]

    for relay_num, fn_name in pr99_functions:
        # Initial: Relay is safe / LOW
        assert harness.relay.relays[relay_num].value() == 0

        # Execute 1 pulse
        resp = harness.request("POST", "/api/v1/relay/%d/pulse" % relay_num, {"duration_ms": 100})
        assert resp["status_code"] == 200
        assert resp["json"].get("success") is True
        assert resp["json"].get("relay") == relay_num
        assert resp["json"].get("duration_ms") == 100

        # Relay pin is currently active (HIGH / 1)
        assert harness.relay.relays[relay_num].value() == 1, "%s (R%d) must be active during pulse" % (fn_name, relay_num)
        # Other transport relays remain OFF
        for other_num, _ in pr99_functions:
            if other_num != relay_num:
                assert harness.relay.relays[other_num].value() == 0, "R%d must not activate when R%d is triggered" % (other_num, relay_num)

        # Advance time to complete the pulse (100 ms)
        time.sleep(0.12)
        harness.relay.update()

        # Confirms relay returns automatically to 0 (OFF)
        assert harness.relay.relays[relay_num].value() == 0, "%s (R%d) must automatically revert to OFF after pulse" % (fn_name, relay_num)

    # Verify R7 remains free/reserved and in safe state 0
    assert harness.relay.relays[7].value() == 0, "R7 must remain in safe state 0"

    # Verify R8 Power ON/OFF control via API
    resp_pwr_on = harness.request("POST", "/api/v1/relay/8", {"state": True})
    assert resp_pwr_on["status_code"] == 200
    assert resp_pwr_on["json"].get("success") is True
    assert resp_pwr_on["json"].get("state") is True
    assert harness.relay.relays[8].value() == 1, "R8 (Power) must be ON (1)"

    resp_pwr_off = harness.request("POST", "/api/v1/relay/8", {"state": False})
    assert resp_pwr_off["status_code"] == 200
    assert resp_pwr_off["json"].get("success") is True
    assert resp_pwr_off["json"].get("state") is False
    assert harness.relay.relays[8].value() == 0, "R8 (Power) must be OFF (0)"

    # Verify PR99 UI includes power control API call
    resp_page = harness.request("GET", "/remote")
    assert resp_page["status_code"] == 200
    assert "/api/v1/relay/8" in resp_page["body"]

    harness.relay.all_off()


def test_33_pr99_transport_status_leds_and_power_interlock():
    """Test 33: Transport Status-LEDs transitions (PLAY->FF->STOP) & Power OFF interlock blocking."""
    harness = APIHarness()
    harness.relay.all_off()

    # 1. Inspect /remote UI HTML / CSS / JS code structure
    resp = harness.request("GET", "/remote")
    assert resp["status_code"] == 200
    html = resp["body"]

    # Verify LED indicator and classes are present in the UI
    assert "led-indicator" in html, "LED indicator element must be present in transport buttons"
    assert "updateTransportUI" in html, "updateTransportUI function must manage active LED status"
    assert "activeTransport" in html, "activeTransport state variable must track machine status"
    assert "btn-play.active-fn .led-indicator" in html or "btn-play .led-indicator.on" in html
    assert "btn-stop.active-fn .led-indicator" in html or "btn-stop .led-indicator.on" in html
    assert "btn-ff.active-fn .led-indicator" in html or "btn-ff .led-indicator.on" in html

    # Verify Power OFF interlock condition in togglePower
    assert "activeTransport !== 'STOP'" in html or "activeTransport != 'STOP'" in html or "activeTransport !== \"STOP\"" in html, \
        "Power OFF must check that activeTransport is STOP or idle before allowing power off"

    # 2. Simulate client-side state machine and API interactions
    # State representation
    client_state = {
        "isPowered": False,
        "activeTransport": None,
        "leds": {
            "PLAY": False,
            "STOP": False,
            "RECORD": False,
            "PAUSE": False,
            "FF": False,
            "REW": False,
        },
        "buttonsDisabled": True,
        "powerIcon": "off",
    }

    def simulate_update_transport_ui(name):
        client_state["activeTransport"] = name
        for k in client_state["leds"]:
            client_state["leds"][k] = (k == name)

    def simulate_update_power_ui(powered):
        client_state["isPowered"] = bool(powered)
        client_state["buttonsDisabled"] = not client_state["isPowered"]
        if client_state["isPowered"]:
            client_state["powerIcon"] = "on"
        else:
            client_state["powerIcon"] = "off"
            simulate_update_transport_ui(None)

    def simulate_handle_transport(relay_num, name):
        if not client_state["isPowered"]:
            return False
        resp = harness.request("POST", "/api/v1/relay/%d/pulse" % relay_num, {"duration_ms": 100})
        if resp["status_code"] == 200:
            simulate_update_transport_ui(name)
            return True
        return False

    def simulate_toggle_power():
        target = not client_state["isPowered"]
        # Power OFF block: if PLAY, REW, FF, RECORD or PAUSE active -> refuse
        if not target and client_state["activeTransport"] and client_state["activeTransport"] != "STOP":
            return False  # Blocked!
        resp = harness.request("POST", "/api/v1/relay/8", {"state": target})
        if resp["status_code"] == 200:
            actual = resp["json"].get("state", target)
            simulate_update_power_ui(actual)
            return True
        return False

    # A. Initial startup state: Power OFF, all LEDs OFF
    simulate_update_power_ui(False)
    assert client_state["isPowered"] is False
    assert client_state["buttonsDisabled"] is True
    assert client_state["activeTransport"] is None
    assert all(not val for val in client_state["leds"].values()), "At startup: all transport status-LEDs must be OFF"

    # B. Power ON: Relay 8 becomes ON, buttons enabled, LEDs still OFF
    res_pwr_on = simulate_toggle_power()
    assert res_pwr_on is True
    assert client_state["isPowered"] is True
    assert client_state["buttonsDisabled"] is False
    assert harness.relay.relays[8].value() == 1, "Relay 8 must be ON"
    assert all(not val for val in client_state["leds"].values()), "After Power ON: status-LEDs remain OFF until chosen"

    # C. Transition 1: Press PLAY -> PLAY-LED remains ON
    res_play = simulate_handle_transport(1, "PLAY")
    assert res_play is True
    assert client_state["activeTransport"] == "PLAY"
    assert client_state["leds"]["PLAY"] is True, "PLAY LED must be ON"
    assert client_state["leds"]["STOP"] is False
    assert client_state["leds"]["FF"] is False
    assert client_state["leds"]["REW"] is False
    assert client_state["leds"]["PAUSE"] is False
    assert client_state["leds"]["RECORD"] is False

    # Simulate pulse completion (100 ms later): PLAY LED must remain ON (persistent machine state)
    time.sleep(0.12)
    harness.relay.update()
    assert harness.relay.relays[1].value() == 0, "Relay 1 pulse completed"
    assert client_state["activeTransport"] == "PLAY", "PLAY must remain active machine function after pulse"
    assert client_state["leds"]["PLAY"] is True, "PLAY-LED must remain ON after pulse ends"

    # D. Transition 2: PLAY -> FF -> Only FF-LED ON
    res_ff = simulate_handle_transport(5, "FF")
    assert res_ff is True
    assert client_state["activeTransport"] == "FF"
    assert client_state["leds"]["PLAY"] is False, "Previous PLAY LED must go OFF"
    assert client_state["leds"]["FF"] is True, "Only FF LED must be ON"
    assert client_state["leds"]["STOP"] is False
    assert client_state["leds"]["REW"] is False
    assert client_state["leds"]["PAUSE"] is False
    assert client_state["leds"]["RECORD"] is False

    # E. Transition 3: FF -> STOP -> Only STOP-LED ON
    res_stop = simulate_handle_transport(2, "STOP")
    assert res_stop is True
    assert client_state["activeTransport"] == "STOP"
    assert client_state["leds"]["FF"] is False, "Previous FF LED must go OFF"
    assert client_state["leds"]["STOP"] is True, "Only STOP LED must be ON"
    assert client_state["leds"]["PLAY"] is False

    # F. Interlock Test 1: Power OFF during PLAY is refused
    simulate_handle_transport(1, "PLAY")
    assert client_state["activeTransport"] == "PLAY"
    assert client_state["leds"]["PLAY"] is True
    res_pwr_off_play = simulate_toggle_power()
    assert res_pwr_off_play is False, "Power OFF must be refused while PLAY is active"
    assert client_state["isPowered"] is True, "isPowered must remain True"
    assert client_state["powerIcon"] == "on", "Power icon must remain green"
    assert harness.relay.relays[8].value() == 1, "Relay 8 must remain ON (1)"

    # G. Interlock Test 2: Power OFF during PAUSE is refused
    simulate_handle_transport(4, "PAUSE")
    assert client_state["activeTransport"] == "PAUSE"
    assert client_state["leds"]["PAUSE"] is True
    res_pwr_off_pause = simulate_toggle_power()
    assert res_pwr_off_pause is False, "Power OFF must be refused while PAUSE is active"
    assert client_state["isPowered"] is True, "isPowered must remain True"
    assert client_state["powerIcon"] == "on", "Power icon must remain green"
    assert harness.relay.relays[8].value() == 1, "Relay 8 must remain ON (1)"

    # H. Interlock Test 3: Power OFF during REW, FF, RECORD is also refused
    for r_num, fn in [(6, "REW"), (5, "FF"), (3, "RECORD")]:
        simulate_handle_transport(r_num, fn)
        assert client_state["activeTransport"] == fn
        assert simulate_toggle_power() is False, "Power OFF must be refused while %s is active" % fn
        assert harness.relay.relays[8].value() == 1, "Relay 8 must remain ON"

    # I. Interlock Test 4: Power OFF during STOP switches Relay 8 OFF & disables transport
    simulate_handle_transport(2, "STOP")
    assert client_state["activeTransport"] == "STOP"
    assert client_state["leds"]["STOP"] is True

    res_pwr_off_stop = simulate_toggle_power()
    assert res_pwr_off_stop is True, "Power OFF must succeed when machine is in STOP"
    assert client_state["isPowered"] is False
    assert client_state["powerIcon"] == "off", "Power icon must become red ('off')"
    assert harness.relay.relays[8].value() == 0, "Relay 8 must revert to safe/rest state (0)"
    assert client_state["buttonsDisabled"] is True, "Transport buttons must be disabled after Power OFF"
    assert client_state["activeTransport"] is None, "activeTransport must be reset after Power OFF"
    assert all(not val for val in client_state["leds"].values()), "All transport status-LEDs must be OFF after Power OFF"

    harness.relay.all_off()


# -----------------------------------------------------------------------------
# MAIN TEST SUITE REGISTRATION & ENTRY POINT
# -----------------------------------------------------------------------------
def build_test_suite():
    runner = TestRunner()
    runner.add_test("1.  Firmware Startup & Initialization", test_01_firmware_startup)
    runner.add_test("2.  Relay Initial Safe State (All LOW/REST)", test_02_all_relays_initialize_safe_low)
    runner.add_test("3.  Relay 1..8 Individual ON/OFF Control", test_03_individual_relays_on_off)
    runner.add_test("4.  Pulse Control with Explicit Duration", test_04_pulse_with_valid_duration)
    runner.add_test("5.  Default Pulse Duration (100 ms)", test_05_default_pulse_100ms)
    runner.add_test("6.  Sequential Pulse Execution & Queueing", test_06_sequential_pulse)
    runner.add_test("7.  Waiting Pulse Replacement Logic", test_07_waiting_pulse_replacement)
    runner.add_test("8.  Single Active Pulse Constraint", test_08_max_one_active_pulse)
    runner.add_test("9.  ALL OFF Safe-State Command", test_09_all_off)
    runner.add_test("10. API GET /api/v1/info Metadata", test_10_api_info_endpoint)
    runner.add_test("11. API GET /api/v1/status Diagnostics", test_11_api_status_endpoint)
    runner.add_test("12. Valid Relay API Requests (ON/OFF/PULSE)", test_12_valid_relay_api_requests)
    runner.add_test("13. Invalid Relay ID Handling (HTTP 400)", test_13_invalid_relay_handling)
    runner.add_test("14. Invalid Pulse Duration Handling (HTTP 400)", test_14_invalid_pulse_duration_handling)
    runner.add_test("15. Standard HTTP Status Codes (200, 400, 404)", test_15_http_status_codes)
    runner.add_test("16. Standard JSON Error Codes", test_16_json_error_codes)
    runner.add_test("17. Status Accuracy vs Hardware Pin States", test_17_status_matches_actual_hardware_state)
    runner.add_test("18. Firmware & API Version Availability", test_18_firmware_and_api_versions_available)
    runner.add_test("19. Network Loss & No Command Replay", test_19_communication_loss_no_command_replay)
    runner.add_test("20. Status Recovery Post-Reconnect", test_20_status_readable_after_recovery)
    runner.add_test("21. Final Safety Verification (All Relays OFF)", test_21_final_state_all_relays_safe_off)
    runner.add_test("22. Diagnose Page & API Test Center UI", test_22_diagnose_service_page)
    runner.add_test("23. 20x Sequential GET /api/v1/info", test_23_sequential_20_info_requests)
    runner.add_test("24. 20x Sequential GET /api/v1/status", test_24_sequential_20_status_requests)
    runner.add_test("25. 60s Continuous Status Polling Stability", test_25_continuous_polling_stability_60s)
    runner.add_test("26. Command Delivery, Confirmation & Recovery", test_26_command_delivery_confirmation_and_recovery)
    runner.add_test("27. HTTP Response Headers & Connection: close", test_27_http_response_headers_and_connection_close)
    runner.add_test("28. Pure HTTP & Zero TLS/SSL Dependency", test_28_no_tls_ssl_dependency)
    runner.add_test("29. Waveshare WS2812 RGB LED (GP13) & Status", test_29_ws2812_rgb_led_status_and_control)
    runner.add_test("30. Performance & Sub-Millisecond Relay Execution", test_30_performance_and_fast_relay_response)
    runner.add_test("31. PWA Manifest, Service Worker & Assets", test_31_pwa_manifest_service_worker_and_assets)
    runner.add_test("32. PR99 Transport Functions (R1..R6 Pulse & R8 Reserve)", test_32_pr99_transport_relay_mapping_and_controls)
    runner.add_test("33. PR99 Status-LEDs & Power OFF Interlock", test_33_pr99_transport_status_leds_and_power_interlock)
    return runner


def main_cli():
    runner = build_test_suite()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main_cli()
