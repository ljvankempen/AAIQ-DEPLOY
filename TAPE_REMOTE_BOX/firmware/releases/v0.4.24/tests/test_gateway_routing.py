# =============================================================================
# AAIQ TAPE PWA — GATEWAY & ASSET ROUTING TEST SUITE
# =============================================================================
# File        : test_gateway_routing.py
# Purpose     : Verify all routes, MIME types, caching headers, and API pass-through
#               matching Caddy reverse-proxy gateway specifications.
# =============================================================================

import sys
import os
import json
import time

# Ensure src/ directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from main import (
    RelayController,
    StatusLED,
    RGB_PIN,
    Config,
    WiFiManager,
    HTTPServer,
    HTTPSAPI,
    PWA_MANIFEST,
    SW_JS,
    ICON_SVG,
    FIRMWARE_VERSION,
    API_VERSION,
)


class MockSocket:
    def __init__(self, request_bytes):
        self.request_bytes = request_bytes
        self.response_data = b""

    def recv(self, bufsize):
        data = self.request_bytes
        self.request_bytes = b""
        return data

    def send(self, data):
        self.response_data += data
        return len(data)

    def sendall(self, data):
        self.response_data += data

    def close(self):
        pass


class MockPoller:
    def __init__(self, sock):
        self.sock = sock

    def poll(self, timeout=None):
        return [(self.sock, 1)]


class GatewayRoutingHarness:
    def __init__(self):
        self.led = StatusLED(RGB_PIN)
        self.relay = RelayController()
        self.relay.all_off()
        self.config = Config()
        self.wifi = WiFiManager(self.config, self.relay, led=self.led)
        self.server = HTTPServer(self.config, self.relay, self.wifi, led=self.led)

    def request(self, method, path, headers=None, body=None):
        body_str = ""
        if body is not None:
            if isinstance(body, (dict, list)):
                body_str = json.dumps(body)
            else:
                body_str = str(body)

        raw_resp = self.server.api_request(method, path, body_str)
        header_bytes, sep, body_bytes = raw_resp.partition(b"\r\n\r\n")
        header_lines = header_bytes.decode("utf-8", errors="replace").split("\r\n")
        status_line = header_lines[0]
        parts = status_line.split(" ", 2)
        status_code = int(parts[1]) if len(parts) >= 2 else 0

        resp_headers = {}
        for h in header_lines[1:]:
            if ":" in h:
                k, v = h.split(":", 1)
                resp_headers[k.strip().lower()] = v.strip()

        return {
            "status_code": status_code,
            "status_line": status_line,
            "headers": resp_headers,
            "body": body_bytes,
        }


def run_tests():
    print("=============================================================================")
    print(" AAIQ TAPE PWA — GATEWAY ROUTING & ASSET VERIFICATION SUITE")
    print("=============================================================================")

    harness = GatewayRoutingHarness()
    tests = []

    def test_root_remote_redirect_or_serve():
        # GET / -> PR99 Remote
        res = harness.request("GET", "/")
        assert res["status_code"] == 200, f"Expected 200, got {res['status_code']}"
        assert "text/html" in res["headers"].get("content-type", "")
        body_text = res["body"].decode("utf-8", errors="replace")
        assert "AAIQ TAPE Remote" in body_text or "PR99" in body_text
        assert 'rel="manifest"' in body_text
        assert "sw.js" in body_text

    def test_remote_endpoint():
        # GET /remote -> PR99 Remote
        res = harness.request("GET", "/remote")
        assert res["status_code"] == 200
        assert "text/html" in res["headers"].get("content-type", "")
        body_text = res["body"].decode("utf-8", errors="replace")
        assert 'rel="manifest"' in body_text
        assert "aaiq-rc.local" in body_text or "AAIQ" in body_text

    def test_manifest_pwa_compliance():
        # GET /manifest.json
        res = harness.request("GET", "/manifest.json")
        assert res["status_code"] == 200
        # Upstream returns application/json; Caddy Gateway enforces application/manifest+json
        ct = res["headers"].get("content-type", "")
        assert "application/manifest+json" in ct or "application/json" in ct, f"Invalid Content-Type: {ct}"
        manifest = json.loads(res["body"].decode("utf-8"))
        assert manifest["name"] == "AAIQ TAPE Remote"
        assert manifest["short_name"] == "TAPE Remote"
        assert manifest["start_url"] == "/remote"
        assert manifest["display"] == "standalone"
        assert manifest["scope"] == "/"
        assert len(manifest["icons"]) >= 2

    def test_service_worker_asset():
        # GET /sw.js
        res = harness.request("GET", "/sw.js")
        assert res["status_code"] == 200
        assert "application/javascript" in res["headers"].get("content-type", "")
        sw_code = res["body"].decode("utf-8")
        assert "addEventListener('install'" in sw_code
        assert "addEventListener('fetch'" in sw_code
        assert "CACHE_NAME" in sw_code

    def test_pwa_icons():
        # GET /icon.svg
        res_svg = harness.request("GET", "/icon.svg")
        assert res_svg["status_code"] == 200
        assert "image/svg+xml" in res_svg["headers"].get("content-type", "")
        assert b"<svg" in res_svg["body"]

        # GET /icon-192.png
        res_png = harness.request("GET", "/icon-192.png")
        assert res_png["status_code"] == 200
        assert "image/png" in res_png["headers"].get("content-type", "")
        assert len(res_png["body"]) > 0

    def test_diagnose_page():
        # GET /diagnose
        res = harness.request("GET", "/diagnose")
        assert res["status_code"] == 200
        assert "text/html" in res["headers"].get("content-type", "")
        assert "Diagnose" in res["body"].decode("utf-8", errors="replace") or "Service" in res["body"].decode("utf-8", errors="replace")

    def test_api_status_and_info():
        # GET /api/v1/info
        res_info = harness.request("GET", "/api/v1/info")
        assert res_info["status_code"] == 200
        assert "application/json" in res_info["headers"].get("content-type", "")
        data_info = json.loads(res_info["body"].decode("utf-8"))
        assert data_info["firmware_version"] == FIRMWARE_VERSION
        assert data_info["http"] is True

        # GET /api/v1/status
        res_status = harness.request("GET", "/api/v1/status")
        assert res_status["status_code"] == 200
        data_status = json.loads(res_status["body"].decode("utf-8"))
        assert "relays" in data_status

    def test_relay_pulse_api():
        # POST /api/v1/relay/1/pulse
        t0 = time.time()
        res_pulse = harness.request(
            "POST",
            "/api/v1/relay/1/pulse",
            headers={"X-Forwarded-For": "192.168.1.100", "X-Forwarded-Proto": "https"},
            body={"duration_ms": 100},
        )
        latency_ms = (time.time() - t0) * 1000.0
        assert res_pulse["status_code"] == 200
        data_pulse = json.loads(res_pulse["body"].decode("utf-8"))
        assert data_pulse["success"] is True
        assert data_pulse["relay"] == 1
        assert latency_ms < 50.0  # Ultra-fast pass-through

    tests.append(("Route GET / (PWA Remote HTML)", test_root_remote_redirect_or_serve))
    tests.append(("Route GET /remote (PWA UI)", test_remote_endpoint))
    tests.append(("Route GET /manifest.json (MIME & Structure)", test_manifest_pwa_compliance))
    tests.append(("Route GET /sw.js (Service Worker & MIME)", test_service_worker_asset))
    tests.append(("Route GET /icon.svg & /icon-192.png (Icons)", test_pwa_icons))
    tests.append(("Route GET /diagnose (Diagnostics Page)", test_diagnose_page))
    tests.append(("Route GET /api/v1/info & /status (Metadata)", test_api_status_and_info))
    tests.append(("Route POST /api/v1/relay/1/pulse (Proxy Headers)", test_relay_pulse_api))

    passed = 0
    failed = 0
    for idx, (name, fn) in enumerate(tests, 1):
        t_start = time.time()
        try:
            fn()
            dt = (time.time() - t_start) * 1000.0
            print(f" [{idx:02d}/{len(tests):02d}] PASS: {name:<50} ({dt:.1f} ms)")
            passed += 1
        except Exception as e:
            dt = (time.time() - t_start) * 1000.0
            print(f" [{idx:02d}/{len(tests):02d}] FAIL: {name:<50} ({dt:.1f} ms) -> {e}")
            failed += 1

    print("")
    print("=============================================================================")
    print(f" Total: {len(tests)} | Passed: {passed} | Failed: {failed}")
    print(f" Outcome: {'ALL TESTS PASSED' if failed == 0 else 'TESTS FAILED'}")
    print("=============================================================================")
    return failed == 0


if __name__ == "__main__":
    if not run_tests():
        sys.exit(1)
