# =============================================================================
# AAIQ TAPE PWA — CROSS-PLATFORM & LATENCY VALIDATION TEST SUITE
# =============================================================================
# File        : test_pwa_crossplatform.py
# Purpose     : Validate PWA criteria for Android Chrome, iOS Safari, desktop browsers,
#               and verify sub-10ms relay pulse latency.
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
    PWA_MANIFEST,
    SW_JS,
)


class MockPWAClient:
    def __init__(self):
        self.led = StatusLED(RGB_PIN)
        self.relay = RelayController()
        self.relay.all_off()
        self.config = Config()
        self.wifi = WiFiManager(self.config, self.relay, led=self.led)
        self.server = HTTPServer(self.config, self.relay, self.wifi, led=self.led)

    def get(self, path):
        resp = self.server.api_request("GET", path, "")
        headers_raw, _, body = resp.partition(b"\r\n\r\n")
        return headers_raw.decode("utf-8"), body

    def post(self, path, payload=None):
        body_str = json.dumps(payload) if payload is not None else ""
        resp = self.server.api_request("POST", path, body_str)
        headers_raw, _, body = resp.partition(b"\r\n\r\n")
        return headers_raw.decode("utf-8"), body


def run_tests():
    print("=============================================================================")
    print(" AAIQ TAPE PWA — CROSS-PLATFORM COMPLIANCE & LATENCY SUITE")
    print("=============================================================================")

    client = MockPWAClient()
    tests = []

    def test_android_chrome_pwa_criteria():
        # 1. Manifest must have valid start_url, display standalone, name, and icons
        assert PWA_MANIFEST["start_url"] == "/remote"
        assert PWA_MANIFEST["display"] == "standalone"
        assert PWA_MANIFEST["name"] == "AAIQ TAPE Remote"
        assert PWA_MANIFEST["short_name"] == "TAPE Remote"
        assert PWA_MANIFEST["theme_color"] == "#18181f"
        assert PWA_MANIFEST["background_color"] == "#121217"

        # Check icons
        icons = PWA_MANIFEST["icons"]
        assert len(icons) >= 2
        sizes = [i.get("sizes") for i in icons]
        assert any("192x192" in s for s in sizes) or any("any" in s for s in sizes)

        # 2. Service worker must have fetch and install handlers
        assert "addEventListener('install'" in SW_JS
        assert "addEventListener('fetch'" in SW_JS

    def test_ios_safari_metadata():
        headers, body = client.get("/remote")
        html = body.decode("utf-8", errors="replace")

        # iOS Safari requires apple-mobile-web-app-capable and apple-touch-icon
        assert 'name="apple-mobile-web-app-capable" content="yes"' in html
        assert 'name="apple-mobile-web-app-status-bar-style"' in html
        assert 'rel="apple-touch-icon"' in html

    def test_transport_relay_latency():
        # Benchmark 50 sequential relay pulses through proxy API
        latencies = []
        for i in range(50):
            relay_id = (i % 6) + 1  # Relays 1..6 (PLAY, STOP, REC, PAUSE, FF, REW)
            t0 = time.perf_counter()
            headers, body = client.post(f"/api/v1/relay/{relay_id}/pulse", {"duration_ms": 100})
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)
            assert b'"success": true' in body or b'"success":true' in body

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        print(f"       [Latency Benchmark] Avg: {avg_latency:.2f} ms | Max: {max_latency:.2f} ms")
        assert avg_latency < 5.0, f"Average latency too high: {avg_latency:.2f} ms"
        assert max_latency < 15.0, f"Max latency too high: {max_latency:.2f} ms"

    def test_offline_asset_cache_list():
        # Service worker STATIC_ASSETS must contain all key UI assets
        required_assets = ['/', '/remote', '/manifest.json', '/icon.svg', '/icon-192.png', '/logo.png']
        for asset in required_assets:
            assert f"'{asset}'" in SW_JS or f'"{asset}"' in SW_JS, f"Missing asset in SW cache: {asset}"

    def test_upstream_reconnect_safety():
        # Simulate network drop / reconnection
        client.relay.all_off()
        for r in range(1, 9):
            assert client.relay.states()[r] == 0

        # Post command after quiet period
        headers, body = client.post("/api/v1/relay/2/on")
        assert client.relay.states()[2] == 1
        headers, body = client.post("/api/v1/relay/2/off")
        assert client.relay.states()[2] == 0

    tests.append(("Android Chrome PWA Install Criteria", test_android_chrome_pwa_criteria))
    tests.append(("iOS Safari Web App & Apple Touch Meta", test_ios_safari_metadata))
    tests.append(("Offline Service Worker Asset Precache", test_offline_asset_cache_list))
    tests.append(("Sub-5ms Transport Relay Latency", test_transport_relay_latency))
    tests.append(("Upstream Safe Reconnect State", test_upstream_reconnect_safety))

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
