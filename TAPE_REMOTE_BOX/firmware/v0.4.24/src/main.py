# =============================================================================
# AAIQ RELAY BOX PICO 2 W
# -----------------------------------------------------------------------------
# File        : main.py
# Version     : 0.4.24
# Platform    : Raspberry Pi Pico 2 W / RP2350
# Firmware    : MicroPython 1.29.0
# Project     : AAIQ RELAY BOX PICO
# -----------------------------------------------------------------------------
# Relay mapping: R1=GP21 R2=GP20 R3=GP19 R4=GP18
#                R5=GP17 R6=GP16 R7=GP15 R8=GP14
# PR99 Remote  : R1=PLAY R2=STOP R3=REC R4=PAUSE R5=FAST_FWD R6=REWIND
#                R7=RESERVE R8=RESERVE (POWER)
# RGB LED WS2812: GP13
# Active relay state: HIGH
# Safe/rest state: LOW
# Default pulse: 100 ms
# API version: v1
# =============================================================================

import gc
import json
import time
import socket
import os
import hashlib

try:
    import machine
except ImportError:
    machine = None

try:
    import rp2
except ImportError:
    rp2 = None

try:
    import network
except ImportError:
    network = None

try:
    import ubinascii
except ImportError:
    import binascii as ubinascii

try:
    import cryptolib
except ImportError:
    try:
        import ucryptolib as cryptolib
    except ImportError:
        cryptolib = None

# MicroPython compatibility shims for time functions when running in standard Python
if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.time() * 1000)
if not hasattr(time, "ticks_add"):
    time.ticks_add = lambda a, b: a + b
if not hasattr(time, "ticks_diff"):
    time.ticks_diff = lambda a, b: a - b
if not hasattr(time, "sleep_ms"):
    time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)

FIRMWARE_VERSION = "0.4.24"
API_VERSION = "v1"
CONFIG_FILE = "config.json"
CONFIG_VERSION = 2

HTTP_PORT = 80
DNS_PORT = 53
SETUP_IP = "192.168.4.1"
SETUP_NETMASK = "255.255.255.0"
SETUP_GATEWAY = "192.168.4.1"
SETUP_DNS = "192.168.4.1"

SETUP_AP_NAME_BASE = "AAIQ-Relay-Setup"
SETUP_AP_SECURITY = 4194308  # WPA2-PSK/AES verified for CYW43 on Pico 2 W / MicroPython 1.29.0
WATCHDOG_TIMEOUT_MS = 10000

DEFAULT_CONFIG = {
    "device_name": "AAIQ Relay Box Pico",
    "wifi": {"ssid_enc": "", "password_enc": ""},
    "pulse": {"default_ms": 100},
}


_CACHED_DEVICE_ID = None
_CACHED_HOSTNAME = None


def device_id():
    global _CACHED_DEVICE_ID
    if _CACHED_DEVICE_ID is None:
        try:
            raw_id = machine.unique_id() if machine and hasattr(machine, "unique_id") else b"\xaa\xbb\xcc\xdd\xee\xff"
            _CACHED_DEVICE_ID = "".join("{:02X}".format(x) for x in raw_id)
        except Exception:
            _CACHED_DEVICE_ID = "UNKNOWN001"
    return _CACHED_DEVICE_ID


def hostname():
    global _CACHED_HOSTNAME
    if _CACHED_HOSTNAME is None:
        dev = device_id()
        suffix = dev[-6:].lower() if len(dev) >= 6 else "001"
        _HOSTNAME = "aaiq-relay-%s.local" % suffix
        _CACHED_HOSTNAME = _HOSTNAME
    return _CACHED_HOSTNAME


def crypto_key():
    # Device-bound AES-128 key. Hardware ID is not stored directly in config.
    raw_id = machine.unique_id() if machine and hasattr(machine, "unique_id") else b"AAIQ-FALLBACK-KEY"
    seed = raw_id + b"|AAIQ-Relay-Box|WIFI|v1"
    return hashlib.sha256(seed).digest()[:16]


def encrypt_secret(value):
    if value is None:
        value = ""
    raw = value.encode("utf-8")
    pad = 16 - (len(raw) % 16)
    raw += bytes([pad]) * pad
    iv = os.urandom(16)
    if cryptolib:
        cipher = cryptolib.aes(crypto_key(), 2, iv)
        encrypted = cipher.encrypt(raw)
    else:
        k = crypto_key()
        encrypted = bytes(b ^ k[i % len(k)] ^ iv[i % 16] for i, b in enumerate(raw))
    return ubinascii.hexlify(iv + encrypted).decode("ascii")


def decrypt_secret(value):
    if not value:
        return ""
    try:
        blob = ubinascii.unhexlify(value)
        if len(blob) < 32 or (len(blob) - 16) % 16 != 0:
            return ""
        iv = blob[:16]
        encrypted = blob[16:]
        if cryptolib:
            cipher = cryptolib.aes(crypto_key(), 2, iv)
            raw = cipher.decrypt(encrypted)
        else:
            k = crypto_key()
            raw = bytes(b ^ k[i % len(k)] ^ iv[i % 16] for i, b in enumerate(encrypted))
        pad = raw[-1]
        if pad < 1 or pad > 16:
            return ""
        if raw[-pad:] != bytes([pad]) * pad:
            return ""
        return raw[:-pad].decode("utf-8")
    except Exception:
        return ""


def default_config():
    return {
        "version": CONFIG_VERSION,
        "device_name": DEFAULT_CONFIG["device_name"],
        "wifi": {"ssid_enc": "", "password_enc": ""},
        "pulse": {"default_ms": 100},
    }


class Config:
    def __init__(self):
        self.data = self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)

            # Migrate old plaintext config if encountered
            old_wifi = data.get("wifi", {}) if isinstance(data, dict) else {}
            if isinstance(old_wifi, dict) and ("ssid" in old_wifi or "password" in old_wifi):
                cfg = default_config()
                cfg["device_name"] = data.get("device_name", DEFAULT_CONFIG["device_name"])
                cfg["wifi"]["ssid_enc"] = encrypt_secret(old_wifi.get("ssid", ""))
                cfg["wifi"]["password_enc"] = encrypt_secret(old_wifi.get("password", ""))
                try:
                    cfg["pulse"]["default_ms"] = int(data.get("pulse", {}).get("default_ms", 100))
                except Exception:
                    pass
                self.data = cfg
                self.save()
                return cfg

            cfg = default_config()
            if isinstance(data, dict):
                if isinstance(data.get("device_name"), str):
                    cfg["device_name"] = data["device_name"]

                wifi = data.get("wifi", {})
                if isinstance(wifi, dict):
                    cfg["wifi"]["ssid_enc"] = wifi.get("ssid_enc", "")
                    cfg["wifi"]["password_enc"] = wifi.get("password_enc", "")

                pulse = data.get("pulse", {})
                if isinstance(pulse, dict):
                    try:
                        value = int(pulse.get("default_ms", 100))
                        if value > 0:
                            cfg["pulse"]["default_ms"] = value
                    except Exception:
                        pass
            return cfg
        except Exception:
            cfg = default_config()
            self._write(cfg)
            return cfg

    def _write(self, cfg):
        tmp = CONFIG_FILE + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(cfg, f)
            try:
                os.remove(CONFIG_FILE)
            except Exception:
                pass
            os.rename(tmp, CONFIG_FILE)
            return True
        except Exception as exc:
            print("CONFIG SAVE ERROR:", exc)
            try:
                os.remove(tmp)
            except Exception:
                pass
            return False

    def save(self):
        return self._write(self.data)

    def wifi_credentials(self):
        wifi = self.data.get("wifi", {})
        return (
            decrypt_secret(wifi.get("ssid_enc", "")),
            decrypt_secret(wifi.get("password_enc", "")),
        )

    def has_wifi(self):
        ssid, _ = self.wifi_credentials()
        return bool(ssid)

    def set_wifi(self, ssid, password):
        self.data["wifi"]["ssid_enc"] = encrypt_secret(ssid)
        self.data["wifi"]["password_enc"] = encrypt_secret(password)
        return self.save()

    def pulse_ms(self):
        try:
            return int(self.data["pulse"].get("default_ms", 100))
        except Exception:
            return 100


RGB_PIN = 13

if rp2 and hasattr(rp2, "asm_pio"):
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
    def _ws2812_pio():
        T1 = 2
        T2 = 5
        T3 = 3
        wrap_target()
        label("bitloop")
        out(x, 1)               .side(0) [T3 - 1]
        jmp(not_x, "do_zero")   .side(1) [T1 - 1]
        jmp("bitloop")          .side(1) [T2 - 1]
        label("do_zero")
        nop()                   .side(0) [T2 - 1]
        wrap()
else:
    _ws2812_pio = None


class StatusLED:
    COLOR_OFF = (0, 0, 0)
    COLOR_RED = (255, 0, 0)
    COLOR_GREEN = (0, 255, 0)
    COLOR_BLUE = (0, 0, 255)
    COLOR_YELLOW = (255, 180, 0)
    COLOR_ORANGE = (255, 80, 0)
    COLOR_PURPLE = (180, 0, 255)
    COLOR_CYAN = (0, 255, 255)
    COLOR_WHITE = (255, 255, 255)

    TRANSPORT_COLORS = {
        1: (0, 255, 0),    # PLAY = groen
        2: (0, 0, 255),    # STOP = blauw
        3: (255, 0, 0),    # RECORD = rood
        4: (255, 80, 0),   # PAUSE = oranje
        5: (0, 255, 255),  # FF = cyaan (R5 / GP17)
        6: (180, 0, 255),  # REW = paars (R6 / GP16)
        8: (0, 255, 0),    # POWER (R8 / GP14)
    }

    def __init__(self, pin=RGB_PIN, brightness=0.25):
        self.pin_num = pin
        self.brightness = brightness
        self.sm = None
        self.current_color = self.COLOR_OFF
        self.status_mode = "starting"
        self.blink_interval_ms = 500
        self.last_blink_tick = time.ticks_ms()
        self.blink_state = True
        self.flash_until = None
        self.flash_color = None

        if rp2 and hasattr(rp2, "StateMachine") and machine and hasattr(machine, "Pin") and _ws2812_pio is not None:
            try:
                self.sm = rp2.StateMachine(0, _ws2812_pio, freq=8_000_000, sideset_base=machine.Pin(self.pin_num))
                self.sm.active(1)
            except Exception as exc:
                print("WS2812 SM INIT ERROR:", exc)
                self.sm = None

    def _show_raw(self, r, g, b):
        self.current_color = (r, g, b)
        if self.sm is None:
            return
        r_scaled = int(r * self.brightness)
        g_scaled = int(g * self.brightness)
        b_scaled = int(b * self.brightness)
        val = (g_scaled << 24) | (r_scaled << 16) | (b_scaled << 8)
        try:
            self.sm.put(val)
        except Exception:
            pass

    def set_color(self, r, g, b):
        self.status_mode = "manual"
        self._show_raw(r, g, b)

    def set_named_color(self, name):
        name = str(name).strip().upper()
        if name in ("RED", "RECORD", "REC", "POWER_OFF", "POWER OFF"):
            self.set_color(*self.COLOR_RED)
        elif name in ("GREEN", "PLAY", "READY", "POWER_ON", "POWER ON", "ONLINE"):
            self.set_color(*self.COLOR_GREEN)
        elif name in ("BLUE", "STOP"):
            self.set_color(*self.COLOR_BLUE)
        elif name in ("YELLOW", "STARTING", "STARTUP", "TEST"):
            self.set_color(*self.COLOR_YELLOW)
        elif name in ("ORANGE", "PAUSE"):
            self.set_color(*self.COLOR_ORANGE)
        elif name in ("PURPLE", "REW", "REWIND", "OTA"):
            self.set_color(*self.COLOR_PURPLE)
        elif name in ("CYAN", "FF", "FAST_FORWARD"):
            self.set_color(*self.COLOR_CYAN)
        elif name == "WHITE":
            self.set_color(*self.COLOR_WHITE)
        elif name == "OFF":
            self.set_color(*self.COLOR_OFF)

    def set_status(self, mode):
        self.status_mode = str(mode).strip().lower()
        self.update(force=True)

    def flash_white(self, duration_ms=150):
        self.flash(self.COLOR_WHITE, duration_ms)

    def flash_transport(self, relay_num, duration_ms=250):
        color = self.TRANSPORT_COLORS.get(relay_num, self.COLOR_WHITE)
        self.flash(color, duration_ms)

    def flash(self, color, duration_ms=150):
        self.flash_color = color
        self.flash_until = time.ticks_add(time.ticks_ms(), duration_ms)
        self._show_raw(*color)

    def update(self, force=False):
        now = time.ticks_ms()

        if self.flash_until is not None:
            if time.ticks_diff(now, self.flash_until) < 0:
                return
            self.flash_until = None
            self.flash_color = None
            force = True

        if self.status_mode in ("startup", "starting", "connecting"):
            if force or self.current_color != self.COLOR_YELLOW:
                self._show_raw(*self.COLOR_YELLOW)
        elif self.status_mode in ("online", "ready", "power_on"):
            if force or self.current_color != self.COLOR_GREEN:
                self._show_raw(*self.COLOR_GREEN)
        elif self.status_mode in ("power_off", "off_standby"):
            if force or self.current_color != self.COLOR_RED:
                self._show_raw(*self.COLOR_RED)
        elif self.status_mode == "play":
            if force or self.current_color != self.COLOR_GREEN:
                self._show_raw(*self.COLOR_GREEN)
        elif self.status_mode == "stop":
            if force or self.current_color != self.COLOR_BLUE:
                self._show_raw(*self.COLOR_BLUE)
        elif self.status_mode in ("record", "rec"):
            if force or self.current_color != self.COLOR_RED:
                self._show_raw(*self.COLOR_RED)
        elif self.status_mode == "pause":
            if force or self.current_color != self.COLOR_ORANGE:
                self._show_raw(*self.COLOR_ORANGE)
        elif self.status_mode in ("rew", "rewind"):
            if force or self.current_color != self.COLOR_PURPLE:
                self._show_raw(*self.COLOR_PURPLE)
        elif self.status_mode in ("ff", "fast_forward"):
            if force or self.current_color != self.COLOR_CYAN:
                self._show_raw(*self.COLOR_CYAN)
        elif self.status_mode in ("error", "fault"):
            if time.ticks_diff(now, self.last_blink_tick) >= self.blink_interval_ms:
                self.last_blink_tick = now
                self.blink_state = not self.blink_state
            if self.blink_state:
                self._show_raw(*self.COLOR_RED)
            else:
                self._show_raw(*self.COLOR_OFF)
        elif self.status_mode == "setup":
            if time.ticks_diff(now, self.last_blink_tick) >= self.blink_interval_ms:
                self.last_blink_tick = now
                self.blink_state = not self.blink_state
            if self.blink_state:
                self._show_raw(*self.COLOR_BLUE)
            else:
                self._show_raw(*self.COLOR_OFF)
        elif self.status_mode == "test":
            if force or self.current_color != self.COLOR_YELLOW:
                self._show_raw(*self.COLOR_YELLOW)
        elif self.status_mode == "ota":
            if force or self.current_color != self.COLOR_PURPLE:
                self._show_raw(*self.COLOR_PURPLE)
        elif self.status_mode == "off":
            if force or self.current_color != self.COLOR_OFF:
                self._show_raw(*self.COLOR_OFF)


RELAY_PINS = {
    1: 21, 2: 20, 3: 19, 4: 18,
    5: 17, 6: 16, 7: 15, 8: 14,
}


class RelayController:
    def __init__(self):
        self.relays = {}
        for number, gpio in RELAY_PINS.items():
            if machine and hasattr(machine, "Pin"):
                pin = machine.Pin(gpio, machine.Pin.OUT, value=0)
            else:
                class MockPin:
                    def __init__(self):
                        self.v = 0
                    def value(self, val=None):
                        if val is not None:
                            self.v = val
                        return self.v
                pin = MockPin()
            pin.value(0)
            self.relays[number] = pin
        self.active_relay = None
        self.active_until = None
        self.active_duration = None
        self.waiting_relay = None
        self.waiting_duration = None
        self._default_duration_fn = lambda: 100

    def set_default_duration_fn(self, fn):
        self._default_duration_fn = fn

    def default_duration(self):
        try:
            return int(self._default_duration_fn())
        except Exception:
            return 100

    def _start(self, relay_number, duration_ms):
        self.relays[relay_number].value(1)
        self.active_relay = relay_number
        self.active_duration = duration_ms
        self.active_until = time.ticks_add(time.ticks_ms(), duration_ms)

    def pulse(self, relay_number, duration_ms=None):
        try:
            relay_number = int(relay_number)
            duration_ms = self.default_duration() if duration_ms is None else int(duration_ms)
        except Exception:
            return False
        if relay_number not in self.relays or duration_ms <= 0:
            return False
        if self.active_relay is None:
            self._start(relay_number, duration_ms)
        else:
            self.waiting_relay = relay_number
            self.waiting_duration = duration_ms
        return True

    def update(self):
        if self.active_relay is None:
            return
        if time.ticks_diff(time.ticks_ms(), self.active_until) >= 0:
            self.relays[self.active_relay].value(0)
            self.active_relay = None
            self.active_until = None
            self.active_duration = None
            if self.waiting_relay is not None:
                relay_number = self.waiting_relay
                duration_ms = self.waiting_duration
                self.waiting_relay = None
                self.waiting_duration = None
                self._start(relay_number, duration_ms)

    def on(self, relay_number):
        try:
            relay_number = int(relay_number)
        except Exception:
            return False
        if relay_number not in self.relays:
            return False
        if self.active_relay == relay_number:
            self.active_relay = None
            self.active_until = None
            self.active_duration = None
        if self.waiting_relay == relay_number:
            self.waiting_relay = None
            self.waiting_duration = None
        self.relays[relay_number].value(1)
        return True

    def off(self, relay_number):
        try:
            relay_number = int(relay_number)
        except Exception:
            return False
        if relay_number not in self.relays:
            return False
        self.relays[relay_number].value(0)
        if self.active_relay == relay_number:
            self.active_relay = None
            self.active_until = None
            self.active_duration = None
        if self.waiting_relay == relay_number:
            self.waiting_relay = None
            self.waiting_duration = None
        return True

    def all_off(self):
        for pin in self.relays.values():
            pin.value(0)
        self.active_relay = None
        self.active_until = None
        self.active_duration = None
        self.waiting_relay = None
        self.waiting_duration = None

    def states(self):
        return {n: p.value() for n, p in self.relays.items()}

    def active(self):
        if self.active_relay is None:
            return None
        remaining = time.ticks_diff(self.active_until, time.ticks_ms())
        if remaining < 0:
            remaining = 0
        return {
            "relay": self.active_relay,
            "duration_ms": self.active_duration,
            "remaining_ms": remaining,
        }

    def waiting(self):
        if self.waiting_relay is None:
            return None
        return {"relay": self.waiting_relay, "duration_ms": self.waiting_duration}


def setup_identity():
    dev = device_id()
    suffix = dev[-6:] if len(dev) >= 6 else "000001"
    pw_suffix = dev[-4:] if len(dev) >= 4 else "0001"
    ap_name = SETUP_AP_NAME_BASE + "-" + suffix
    ap_password = ("AAIQ" + pw_suffix)[:8]
    if len(ap_password) < 8:
        ap_password = (ap_password + "12345678")[:8]
    return ap_name, ap_password


def scan_wifi_networks():
    if not network:
        return []
    try:
        sta = network.WLAN(network.STA_IF)
        if not sta.active():
            sta.active(True)
        return sta.scan()
    except Exception as exc:
        print("WIFI SCAN ERROR:", exc)
        return []


class WiFiManager:
    def __init__(self, config, relay, on_mode_change=None, led=None):
        self.config = config
        self.relay = relay
        self.on_mode_change = on_mode_change
        self.led = led
        self.sta = network.WLAN(network.STA_IF) if network else None
        self.ap = network.WLAN(network.AP_IF) if network else None
        self.setup_mode = False
        self.setup_ap_name, self.setup_ap_password = setup_identity()
        self.last_attempt = 0
        self.retry_ms = 10000
        self.failed_attempts = 0
        self.max_failed_attempts = 3
        self.was_connected = False
        self.cached_ip = None
        self.cached_mask = None
        self.cached_gateway = None
        self.cached_dns = None
        self.cached_ssid = None

    def _refresh_cached_sta(self):
        if self.sta and self.sta.isconnected():
            try:
                self.cached_ip, self.cached_mask, self.cached_gateway, self.cached_dns = self.sta.ifconfig()
            except Exception:
                pass
            try:
                self.cached_ssid = self.sta.config("essid")
            except Exception:
                self.cached_ssid = self.config.wifi_credentials()[0]

    def start(self):
        if not self.config.has_wifi():
            self.enter_setup_mode()
            return

        if self.led:
            self.led.set_status("startup")

        print("WIFI: Initializing Station Interface...")
        if self.ap:
            try:
                self.ap.active(False)
            except Exception:
                pass

        if self.sta:
            self.sta.active(True)

        ssid, password = self.config.wifi_credentials()
        print("WIFI: Connecting to saved network '%s'..." % ssid)
        connected = self._blocking_connect(ssid, password, timeout_s=15)
        if not connected:
            print("WIFI: Connection to '%s' failed! Falling back to Setup Mode." % ssid)
            self.enter_setup_mode()
        elif self.led:
            self.led.set_status("online")

    def _blocking_connect(self, ssid, password, timeout_s=15):
        if not self.sta:
            return False
        try:
            self.sta.active(True)
            self.sta.connect(ssid, password)
        except Exception as exc:
            print("WIFI INITIAL CONNECT ERROR:", exc)
            return False

        start_tick = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_tick) < timeout_s * 1000:
            if self.sta.isconnected():
                self.was_connected = True
                self.failed_attempts = 0
                self._refresh_cached_sta()
                print("==============================================")
                print("WIFI CONNECTED SUCCESSFULLY!")
                print("SSID     :", ssid)
                print("IP       :", self.cached_ip)
                print("Netmask  :", self.cached_mask)
                print("Gateway  :", self.cached_gateway)
                print("DNS      :", self.cached_dns)
                print("Hostname :", hostname())
                print("==============================================")
                return True
            time.sleep_ms(200)
        return False

    def connect(self):
        ssid, password = self.config.wifi_credentials()
        if not ssid or not self.sta:
            return False
        try:
            self.sta.active(True)
            if self.sta.isconnected():
                if not self.was_connected:
                    self.was_connected = True
                    self.failed_attempts = 0
                    self._refresh_cached_sta()
                    print("WIFI CONNECTED: IP is", self.cached_ip)
                return True
            print("WIFI: Reconnecting to '%s' (attempt %d)..." % (ssid, self.failed_attempts + 1))
            self.sta.connect(ssid, password)
            self.last_attempt = time.ticks_ms()
            return True
        except Exception as exc:
            print("WIFI RECONNECT ERROR:", exc)
            return False

    def enter_setup_mode(self):
        self.setup_mode = True
        self.relay.all_off()
        if self.led:
            self.led.set_status("setup")
        self.cached_ip = None
        self.cached_mask = None
        self.cached_gateway = None
        self.cached_dns = None
        self.cached_ssid = None
        if self.sta:
            try:
                self.sta.active(False)
            except Exception:
                pass

        if self.ap:
            try:
                self.ap.active(False)
                self.ap.active(True)
                self.ap.ifconfig((SETUP_IP, SETUP_NETMASK, SETUP_GATEWAY, SETUP_DNS))
                self.ap.config(
                    essid=self.setup_ap_name,
                    password=self.setup_ap_password,
                    security=SETUP_AP_SECURITY,
                )
            except Exception as exc:
                print("SETUP AP ERROR:", exc)

        print("==============================================")
        print("WIFI SETUP MODE ACTIVATED")
        print("AP SSID     :", self.setup_ap_name)
        print("AP Password :", self.setup_ap_password)
        print("AP IP       :", SETUP_IP)
        print("Security    : WPA2-PSK/AES (%d)" % SETUP_AP_SECURITY)
        print("==============================================")

        if self.on_mode_change:
            try:
                self.on_mode_change(True)
            except Exception:
                pass

    def update(self):
        if self.setup_mode:
            self.relay.all_off()
            return
        if not self.sta:
            return

        if self.sta.isconnected():
            if not self.was_connected or not self.cached_ip:
                self.was_connected = True
                self.failed_attempts = 0
                self._refresh_cached_sta()
                if self.led:
                    self.led.set_status("online")
                print("WIFI: Reconnected successfully! IP:", self.cached_ip)
            return

        if self.was_connected:
            print("WIFI: Connection lost!")
            self.was_connected = False
            if self.led:
                self.led.set_status("connecting")
            self.cached_ip = None
            self.cached_mask = None
            self.cached_gateway = None
            self.cached_dns = None
            self.cached_ssid = None
            self.last_attempt = time.ticks_ms()
            self.failed_attempts = 0

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_attempt) >= self.retry_ms:
            self.failed_attempts += 1
            if self.failed_attempts > self.max_failed_attempts:
                print("WIFI: Max reconnect attempts reached. Falling back to Setup Mode.")
                self.enter_setup_mode()
            else:
                self.connect()

    def connected(self):
        return self.sta.isconnected() if self.sta else False

    def info(self):
        if self.setup_mode:
            ip = self.ap.ifconfig()[0] if self.ap else SETUP_IP
            return {
                "mode": "setup",
                "ssid": self.setup_ap_name,
                "ip": ip,
                "security": "WPA2-PSK/AES",
            }
        if self.sta and self.sta.isconnected():
            if not self.cached_ip:
                self._refresh_cached_sta()
            return {
                "mode": "station",
                "ssid": self.cached_ssid or self.config.wifi_credentials()[0],
                "ip": self.cached_ip,
                "mask": self.cached_mask,
                "gateway": self.cached_gateway,
                "dns": self.cached_dns,
                "connected": True,
            }
        return {
            "mode": "station",
            "ssid": self.config.wifi_credentials()[0],
            "ip": None,
            "connected": False,
        }


def html_escape(value):
    return (
        str(value).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
    )


def url_decode(value):
    value = value.replace("+", " ")
    result = ""
    i = 0
    while i < len(value):
        if value[i] == "%" and i + 2 < len(value):
            try:
                result += chr(int(value[i + 1:i + 3], 16))
                i += 3
                continue
            except Exception:
                pass
        result += value[i]
        i += 1
    return result


def parse_form(body):
    result = {}
    if not body:
        return result
    for item in body.split("&"):
        if "=" in item:
            key, value = item.split("=", 1)
            result[url_decode(key)] = url_decode(value)
    return result


def parse_body_dict(body):
    if not body:
        return {}
    b = body.strip()
    if b.startswith("{") and b.endswith("}"):
        try:
            return json.loads(b)
        except Exception:
            pass
    return parse_form(b)


def response(body, status="200 OK", content_type="text/html", extra=""):
    if isinstance(body, dict):
        body = json.dumps(body)
        content_type = "application/json"
    if isinstance(body, str):
        body = body.encode("utf-8")
    extra_str = ("\r\n" + extra.strip()) if (extra and extra.strip()) else ""
    header = (
        "HTTP/1.1 " + status + "\r\n"
        "Content-Type: " + content_type + "; charset=utf-8\r\n"
        "Content-Length: " + str(len(body)) + "\r\n"
        "Connection: close" + extra_str + "\r\n\r\n"
    )
    return header.encode("utf-8") + body


def send_response(sock, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    total = 0
    length = len(data)
    t0 = time.ticks_ms()
    while total < length and time.ticks_diff(time.ticks_ms(), t0) < 6000:
        chunk = data[total:total + 1024]
        try:
            if hasattr(sock, "send"):
                sent = sock.send(chunk)
            elif hasattr(sock, "write"):
                sent = sock.write(chunk)
            elif hasattr(sock, "sendall"):
                sock.sendall(chunk)
                sent = len(chunk)
            else:
                sent = sock.send(chunk)

            if sent is None:
                sent = len(chunk)
            if sent > 0:
                total += sent
            else:
                time.sleep_ms(2)
        except OSError as exc:
            err = getattr(exc, "args", [None])[0]
            if err in (11, 110) or "eagain" in str(exc).lower() or "etimedout" in str(exc).lower() or "timed out" in str(exc).lower():
                time.sleep_ms(5)
            else:
                print("[HTTP TX ERROR] OSError:", exc)
                break
        except Exception as exc:
            print("[HTTP TX ERROR]:", exc)
            break


def setup_page(networks):
    options = ""
    seen = set()
    for item in networks:
        try:
            raw_ssid = item[0]
            ssid = raw_ssid.decode("utf-8") if isinstance(raw_ssid, bytes) else str(raw_ssid)
            ssid = ssid.strip()
            if ssid and ssid not in seen:
                seen.add(ssid)
                options += '<option value="%s">%s</option>' % (
                    html_escape(ssid), html_escape(ssid)
                )
        except Exception:
            pass

    return """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AAIQ Relay Box Wi-Fi Setup</title>
<style>
body{font-family:Arial,sans-serif;max-width:520px;margin:25px auto;padding:20px;background:#f8f9fa;color:#333}
.card{background:#fff;padding:24px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
h1{margin-top:0;font-size:22px;color:#111}
input,select{width:100%%;box-sizing:border-box;padding:12px;margin:8px 0 16px;border:1px solid #ccc;border-radius:4px;font-size:16px}
.pw{position:relative;width:100%%}
.pw input{padding-right:48px}
.eye{position:absolute;right:6px;top:6px;width:40px;height:40px;padding:0;margin:0;font-size:18px;background:none;border:none;cursor:pointer}
button.submit{width:100%%;padding:14px;font-size:16px;font-weight:bold;background:#0066cc;color:#fff;border:none;border-radius:4px;cursor:pointer}
button.submit:hover{background:#0052a3}
.note{padding:12px;background:#e7f3fe;border-left:4px solid #0066cc;border-radius:4px;margin-bottom:20px;font-size:14px}
</style></head><body>
<div class="card">
<h1>AAIQ Relay Box</h1>
<div class="note"><b>Wi-Fi Setup Portal</b><br>Select or enter the 2.4 GHz Wi-Fi network for this Relay Box Pico 2 W.</div>
<form method="POST" action="/setup" autocomplete="off" novalidate>
<label for="ssid"><b>Wi-Fi Network (SSID)</b></label>
<input id="ssid" name="ssid" type="text" required autocomplete="new-password"
       autocapitalize="none" autocorrect="off" spellcheck="false"
       placeholder="Select or enter SSID" list="wifiNetworks">
<datalist id="wifiNetworks">%s</datalist>

<label for="password"><b>Wi-Fi Password</b></label>
<div class="pw">
<input id="password" name="password" type="password" autocomplete="new-password"
       autocapitalize="none" autocorrect="off" spellcheck="false"
       placeholder="Enter Wi-Fi password">
<button class="eye" type="button" onclick="togglePassword()" aria-label="Show password">◉</button>
</div>
<button class="submit" type="submit">Save & Connect</button>
<script>
function togglePassword(){
  var p=document.getElementById("password");
  var b=document.querySelector(".eye");
  if(p.type==="password"){p.type="text";b.textContent="○";}
  else{p.type="password";b.textContent="◉";}
}
</script>
</form>
</div>
</body></html>""" % options


PWA_MANIFEST = {
    "name": "AAIQ TAPE Remote",
    "short_name": "TAPE Remote",
    "description": "AAIQ Tape Remote Control",
    "start_url": "/remote",
    "scope": "/",
    "display": "standalone",
    "orientation": "any",
    "background_color": "#121217",
    "theme_color": "#18181f",
    "icons": [
        {
            "src": "/icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        },
        {
            "src": "/icon.svg",
            "sizes": "192x192 512x512",
            "type": "image/svg+xml",
            "purpose": "any"
        }
    ]
}

SW_JS = """const CACHE_NAME = 'tape-remote-v0424';
const STATIC_ASSETS = ['/', '/remote', '/manifest.json', '/icon.svg', '/icon-192.png', '/logo.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request));
    return;
  }
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
"""

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1c1c26"/>
      <stop offset="100%" stop-color="#0e0e14"/>
    </linearGradient>
    <linearGradient id="metal" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#e2e8f0"/>
      <stop offset="50%" stop-color="#94a3b8"/>
      <stop offset="100%" stop-color="#475569"/>
    </linearGradient>
    <linearGradient id="hub" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#334155"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="100" fill="url(#bg)"/>
  <rect x="20" y="20" width="472" height="472" rx="80" fill="none" stroke="#334155" stroke-width="4"/>
  <g transform="translate(160, 205)">
    <circle r="100" fill="#1e293b" stroke="url(#metal)" stroke-width="7"/>
    <circle r="72" fill="none" stroke="#475569" stroke-width="3" stroke-dasharray="14,8"/>
    <circle r="40" fill="url(#hub)" stroke="url(#metal)" stroke-width="5"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b" transform="rotate(60)"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b" transform="rotate(120)"/>
    <circle r="16" fill="#0f172a" stroke="url(#metal)" stroke-width="3"/>
    <circle r="5" fill="#f8fafc"/>
  </g>
  <g transform="translate(352, 205)">
    <circle r="100" fill="#1e293b" stroke="url(#metal)" stroke-width="7"/>
    <circle r="72" fill="none" stroke="#475569" stroke-width="3" stroke-dasharray="14,8"/>
    <circle r="40" fill="url(#hub)" stroke="url(#metal)" stroke-width="5"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b" transform="rotate(60)"/>
    <rect x="-6" y="-34" width="12" height="68" rx="3" fill="#64748b" transform="rotate(120)"/>
    <circle r="16" fill="#0f172a" stroke="url(#metal)" stroke-width="3"/>
    <circle r="5" fill="#f8fafc"/>
  </g>
  <path d="M 160 305 C 220 350, 292 350, 352 305" fill="none" stroke="#64748b" stroke-width="6"/>
  <rect x="226" y="318" width="60" height="32" rx="4" fill="url(#metal)" stroke="#334155" stroke-width="2"/>
  <rect x="238" y="327" width="36" height="14" rx="2" fill="#0f172a"/>
  <text x="256" y="72" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" font-size="32" font-weight="900" fill="#f8fafc" letter-spacing="4">REVOX</text>
  <text x="256" y="102" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" font-size="18" font-weight="700" fill="#00b4d8" letter-spacing="3">TAPE REMOTE</text>
  <g transform="translate(64, 385)">
    <rect width="384" height="65" rx="10" fill="#181822" stroke="#334155" stroke-width="2"/>
    <circle cx="50" cy="32" r="13" fill="#3b82f6"/>
    <circle cx="120" cy="32" r="13" fill="#3b82f6"/>
    <circle cx="192" cy="32" r="13" fill="#f59e0b"/>
    <circle cx="264" cy="32" r="15" fill="#22c55e"/>
    <circle cx="334" cy="32" r="13" fill="#ef4444"/>
  </g>
</svg>"""

_CACHED_LOGO_BYTES = None


def get_logo_data():
    global _CACHED_LOGO_BYTES
    if _CACHED_LOGO_BYTES is not None:
        return _CACHED_LOGO_BYTES
    candidates = [
        "images/logo.png",
        "logo.png",
        "/images/logo.png",
        "/logo.png",
        "../images/logo.png",
    ]
    try:
        if "__file__" in globals() and __file__:
            base_d = os.path.dirname(__file__)
            candidates.append(os.path.join(base_d, "..", "images", "logo.png"))
            candidates.append(os.path.join(base_d, "images", "logo.png"))
            candidates.append(os.path.join(base_d, "logo.png"))
    except Exception:
        pass

    for fpath in candidates:
        try:
            with open(fpath, "rb") as f:
                data = f.read()
                if data and len(data) > 0:
                    _CACHED_LOGO_BYTES = data
                    return data
        except Exception:
            pass
    return b""


LOGO_PNG_BYTES = get_logo_data()

ICON_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa"
    b"\x00\x00\x00\x19IDATx\x9cc\xfc\xff\xff?\x03\x10\x04\x00\x00\xff\xff\x03\x00\x00\x01\x00\x01\x18\xdd\x8d\xb0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def pr99_remote_page(config, relay, wifi):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#121217">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TAPE Remote">
<meta name="application-name" content="TAPE Remote">
<title>AAIQ TAPE Remote</title>
<link rel="manifest" href="/manifest.json">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<link rel="alternate icon" type="image/png" href="/icon-192.png">
<link rel="apple-touch-icon" href="/icon.svg">
<link rel="apple-touch-icon" sizes="192x192" href="/icon-192.png">
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:#101015;
  color:#f1f5f9;
  min-height:100vh;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:flex-start;
  padding:12px;
  user-select:none;
}
.container{
  width:100%%;
  max-width:540px;
  background:#181820;
  border:1px solid #2e2e3d;
  border-radius:14px;
  box-shadow:0 8px 30px rgba(0,0,0,0.6);
  position:relative;
  display:flex;
  flex-direction:column;
}
.header{
  position:relative;
  background:#1a1a24;
  min-height:78px;
  padding:10px 16px;
  border-bottom:1px solid #2e2e3d;
  border-top-left-radius:14px;
  border-top-right-radius:14px;
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
}
.brand-logo-container{
  flex:1;
  min-width:0;
  display:flex;
  align-items:center;
  justify-content:flex-start;
  height:100%%;
  overflow:hidden;
  pointer-events:none;
  user-select:none;
}
.header-logo{
  max-height:64px;
  max-width:100%%;
  width:auto;
  height:auto;
  object-fit:contain;
  object-position:left center;
  display:block;
  background:transparent;
  pointer-events:none;
}
.header-actions{
  position:relative;
  z-index:50;
  display:flex;
  align-items:center;
  gap:8px;
  flex-shrink:0;
}
@media (max-width: 400px){
  .header{
    min-height:70px;
    padding:8px 12px;
    gap:8px;
  }
  .header-logo{
    max-height:54px;
  }
}
.btn-install{
  background:#0284c7;
  color:#fff;
  border:none;
  padding:5px 12px;
  border-radius:6px;
  font-size:12px;
  font-weight:700;
  cursor:pointer;
  display:none;
}
.btn-install:hover{background:#0369a1;}
.menu-container{
  position:relative;
  z-index:60;
}
.btn-power{
  background:none;
  border:none;
  padding:4px;
  cursor:pointer;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#ef4444;
  outline:none;
  transition:color 0.2s ease, transform 0.12s ease, filter 0.2s ease;
  -webkit-tap-highlight-color:transparent;
}
.btn-power:hover{
  transform:scale(1.1);
}
.btn-power:active{
  transform:scale(0.95);
}
.btn-power.off{
  color:#ef4444;
}
.btn-power.on{
  color:#22c55e;
  filter:drop-shadow(0 0 6px rgba(34,197,94,0.6));
}
.btn-power .pwr-icon{
  width:24px;
  height:24px;
  display:block;
}
.btn-menu{
  background:none;
  color:#cbd5e1;
  border:none;
  width:36px;
  height:36px;
  border-radius:6px;
  font-size:22px;
  font-weight:700;
  display:flex;
  align-items:center;
  justify-content:center;
  cursor:pointer;
  transition:color 0.15s, background 0.15s;
  line-height:1;
  outline:none;
  -webkit-tap-highlight-color:transparent;
}
.btn-menu:hover, .btn-menu.active{
  background:rgba(56,189,248,0.12);
  color:#38bdf8;
  border:none;
}
.dropdown-menu{
  display:none;
  position:absolute;
  top:calc(100%% + 8px);
  right:0;
  background:#1e1e28;
  border:1px solid #3e3e52;
  border-radius:8px;
  box-shadow:0 10px 25px rgba(0,0,0,0.75);
  min-width:160px;
  z-index:1000;
  overflow:hidden;
}
.dropdown-menu.show{
  display:flex;
  flex-direction:column;
}
.dropdown-item{
  display:flex;
  align-items:center;
  gap:8px;
  padding:10px 14px;
  color:#f1f5f9;
  text-decoration:none;
  font-size:13px;
  font-weight:600;
  background:none;
  border:none;
  width:100%%;
  text-align:left;
  cursor:pointer;
  transition:background 0.15s, color 0.15s;
  font-family:inherit;
}
.dropdown-item:hover{
  background:#2e2e40;
  color:#38bdf8;
}
.dropdown-item:not(:last-child){
  border-bottom:1px solid #282836;
}

.deck-view{
  background:#14141c;
  padding:16px 20px;
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:12px;
  border-bottom:1px solid #23232f;
}
.reels-container{
  display:flex;
  justify-content:space-around;
  align-items:center;
  width:100%%;
  max-width:380px;
  padding:8px 0;
}
.reel{
  width:110px;
  height:110px;
  border-radius:50%%;
  background:radial-gradient(circle at center, #2b2b38 0%%, #1c1c24 60%%, #121218 100%%);
  border:3px solid #3f3f54;
  box-shadow:inset 0 0 12px rgba(0,0,0,0.8), 0 4px 10px rgba(0,0,0,0.5);
  position:relative;
}
.reel.spinning{animation:spinReel 1.2s linear infinite;}
.reel.spinning-fast{animation:spinReel 0.4s linear infinite;}
.reel.spinning-rev{animation:spinReelRev 0.4s linear infinite;}
@keyframes spinReel{from{transform:rotate(360deg);}to{transform:rotate(0deg);}}
@keyframes spinReelRev{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
.reel-hub{
  position:absolute;
  top:50%%;left:50%%;
  width:36px;height:36px;
  margin:-18px 0 0 -18px;
  border-radius:50%%;
  background:#3b3b4d;
  border:2px solid #56566d;
}
.reel-slot{
  position:absolute;
  top:12px;left:50%%;
  width:8px;height:24px;
  margin-left:-4px;
  background:#0e0e13;
  border-radius:3px;
  transform-origin:50%% 43px;
}
.reel-slot.s2{transform:rotate(120deg);}
.reel-slot.s3{transform:rotate(240deg);}
.reel-center-pin{
  position:absolute;
  top:50%%;left:50%%;
  width:12px;height:12px;
  margin:-6px 0 0 -6px;
  border-radius:50%%;
  background:#94a3b8;
  border:1px solid #fff;
}

.transport-section{
  padding:16px;
  display:flex;
  flex-direction:column;
  gap:16px;
}
.btn-grid{
  display:grid;
  grid-template-columns:repeat(3, 1fr);
  gap:12px;
}
.btn-t{
  background:linear-gradient(180deg,#242433 0%%,#181822 100%%);
  border:1px solid #343447;
  border-radius:10px;
  padding:16px 8px 12px;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:6px;
  cursor:pointer;
  transition:all 0.12s ease;
  box-shadow:0 4px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
  position:relative;
  overflow:hidden;
}
.btn-t:disabled{
  opacity:0.4;
  cursor:not-allowed;
  filter:grayscale(60%%);
  box-shadow:none;
}
.btn-t:hover:not(:disabled){
  background:linear-gradient(180deg,#2c2c3e 0%%,#1f1f2c 100%%);
  border-color:#4a4a66;
  transform:translateY(-1px);
}
.btn-t.active, .btn-t.pressed, .btn-t:active:not(:disabled){
  transform:translateY(2px);
  box-shadow:inset 0 3px 6px rgba(0,0,0,0.7);
}
.led-indicator{
  position:absolute;
  top:6px;right:6px;
  width:6px;height:6px;
  border-radius:50%%;
  background:#334155;
  pointer-events:none;
  transition:background 0.15s ease, box-shadow 0.15s ease;
}
.btn-icon{
  font-size:24px;
  line-height:1;
}
.btn-label{
  font-size:12px;
  font-weight:800;
  letter-spacing:1px;
  color:#f1f5f9;
}

.btn-play:hover:not(:disabled){border-color:#22c55e;}
.btn-play .btn-icon{color:#22c55e;}
.btn-play.active-fn .led-indicator, .btn-play .led-indicator.on, .btn-play.active .led-indicator, .btn-play:active:not(:disabled) .led-indicator{
  background:#22c55e;
  box-shadow:0 0 6px #22c55e;
}

.btn-stop:hover:not(:disabled){border-color:#cbd5e1;}
.btn-stop .btn-icon{color:#e2e8f0;}
.btn-stop.active-fn .led-indicator, .btn-stop .led-indicator.on, .btn-stop.active .led-indicator, .btn-stop:active:not(:disabled) .led-indicator{
  background:#e2e8f0;
  box-shadow:0 0 6px #e2e8f0;
}

.btn-pause:hover:not(:disabled){border-color:#f59e0b;}
.btn-pause .btn-icon{color:#f59e0b;}
.btn-pause.active-fn .led-indicator, .btn-pause .led-indicator.on, .btn-pause.active .led-indicator, .btn-pause:active:not(:disabled) .led-indicator{
  background:#f59e0b;
  box-shadow:0 0 6px #f59e0b;
}

.btn-rec:hover:not(:disabled){border-color:#ef4444;}
.btn-rec .btn-icon{color:#ef4444;}
.btn-rec.active-fn .led-indicator, .btn-rec .led-indicator.on, .btn-rec.active .led-indicator, .btn-rec:active:not(:disabled) .led-indicator{
  background:#ef4444;
  box-shadow:0 0 6px #ef4444;
}

.btn-rew:hover:not(:disabled), .btn-ff:hover:not(:disabled){border-color:#38bdf8;}
.btn-rew .btn-icon, .btn-ff .btn-icon{color:#38bdf8;}
.btn-rew.active-fn .led-indicator, .btn-rew .led-indicator.on, .btn-rew.active .led-indicator, .btn-rew:active:not(:disabled) .led-indicator,
.btn-ff.active-fn .led-indicator, .btn-ff .led-indicator.on, .btn-ff.active .led-indicator, .btn-ff:active:not(:disabled) .led-indicator{
  background:#38bdf8;
  box-shadow:0 0 6px #38bdf8;
}

.btn-play.active-fn{border-color:#22c55e;}
.btn-stop.active-fn{border-color:#94a3b8;}
.btn-pause.active-fn{border-color:#f59e0b;}
.btn-rec.active-fn{border-color:#ef4444;}
.btn-rew.active-fn, .btn-ff.active-fn{border-color:#38bdf8;}

.btn-play.pressed, .btn-play:active:not(:disabled){
  background:linear-gradient(180deg,#143a24 0%%,#0b2416 100%%);
  border-color:#22c55e;
}
.btn-stop.pressed, .btn-stop:active:not(:disabled){
  background:linear-gradient(180deg,#30343f 0%%,#1d2027 100%%);
  border-color:#94a3b8;
}
.btn-pause.pressed, .btn-pause:active:not(:disabled){
  background:linear-gradient(180deg,#3d290c 0%%,#261805 100%%);
  border-color:#f59e0b;
}
.btn-rec.pressed, .btn-rec:active:not(:disabled){
  background:linear-gradient(180deg,#3d1216 0%%,#26090c 100%%);
  border-color:#ef4444;
}
.btn-rew.pressed, .btn-rew:active:not(:disabled),
.btn-ff.pressed, .btn-ff:active:not(:disabled){
  background:linear-gradient(180deg,#0f2747 0%%,#09172a 100%%);
  border-color:#3b82f6;
}

.app-modal{
  position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,0.8);
  display:none;justify-content:center;align-items:center;
  z-index:999;padding:15px;
}
.app-modal-content{
  background:#1e1e28;
  border:1px solid #3e3e52;
  border-radius:12px;
  width:100%%;
  max-width:360px;
  padding:18px 20px;
  color:#f1f5f9;
  display:flex;
  flex-direction:column;
  gap:14px;
}
.modal-header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  border-bottom:1px solid #2e2e3d;
  padding-bottom:8px;
}
.modal-close{
  background:none;
  border:none;
  color:#94a3b8;
  font-size:22px;
  cursor:pointer;
  padding:0 4px;
  line-height:1;
}
.modal-close:hover{color:#fff;}
.info-list{
  display:flex;
  flex-direction:column;
  gap:10px;
  font-size:13px;
}
.info-row{
  display:flex;
  justify-content:space-between;
  padding:4px 0;
  border-bottom:1px solid #282836;
}
.info-label{color:#94a3b8;font-weight:600;}
.info-val{color:#f1f5f9;font-weight:700;font-family:monospace;}
.btn-modal-action{
  background:#0284c7;
  color:#fff;
  border:none;
  padding:8px 18px;
  border-radius:6px;
  font-weight:700;
  cursor:pointer;
  align-self:flex-end;
}
.btn-modal-action:hover{background:#0369a1;}

.ios-modal{
  position:fixed;top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,0.8);
  display:none;justify-content:center;align-items:center;
  z-index:999;padding:15px;
}
.ios-modal-content{
  background:#1e1e28;
  border:1px solid #3e3e52;
  border-radius:12px;
  max-width:380px;
  width:100%%;
  padding:20px;
  color:#f1f5f9;
  text-align:center;
  display:flex;
  flex-direction:column;
  gap:12px;
}
.ios-modal-content h3{margin-bottom:0;color:#38bdf8;font-size:16px;}
.ios-modal-content p{font-size:13px;color:#cbd5e1;line-height:1.5;}
.ios-modal-content button{
  background:#0284c7;color:#fff;border:none;padding:8px 18px;border-radius:6px;font-weight:700;cursor:pointer;align-self:center;
}
.ios-modal-content button:hover{background:#0369a1;}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="brand-logo-container">
      <img id="headerLogo" src="/logo.png?v=%s" class="header-logo" alt="AAIQ Tape Remote Control">
    </div>
    <div class="header-actions">
      <button id="btnInstall" class="btn-install" onclick="promptInstall()">&#128242; Install App</button>
      <button id="btnPower" class="btn-power off" onclick="togglePower()" title="Power" aria-label="Power">
        <svg class="pwr-icon" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2v10"></path>
          <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
        </svg>
      </button>
      <div class="menu-container">
        <button id="btnMenu" class="btn-menu" onclick="toggleMenu()" title="Menu" aria-label="Menu">&#8942;</button>
        <div id="dropdownMenu" class="dropdown-menu">
          <button id="menuItemInstall" class="dropdown-item" onclick="promptInstall(); toggleMenu(false);">&#128242; App Installeren</button>
          <a href="/diagnose" class="dropdown-item">&#9881; Diagnose</a>
          <button class="dropdown-item" onclick="toggleInfoModal(true); toggleMenu(false);">&#9432; Info</button>
        </div>
      </div>
    </div>
  </div>

  <div class="deck-view">
    <div class="reels-container">
      <div id="reelLeft" class="reel">
        <div class="reel-slot"></div>
        <div class="reel-slot s2"></div>
        <div class="reel-slot s3"></div>
        <div class="reel-hub"></div>
        <div class="reel-center-pin"></div>
      </div>
      <div id="reelRight" class="reel">
        <div class="reel-slot"></div>
        <div class="reel-slot s2"></div>
        <div class="reel-slot s3"></div>
        <div class="reel-hub"></div>
        <div class="reel-center-pin"></div>
      </div>
    </div>
  </div>

  <div class="transport-section">
    <div class="btn-grid">
      <!-- ROW 1: REW, PLAY, FF -->
      <button id="btn-r6" class="btn-t btn-rew" disabled onclick="handleTransport(6, 'REW', 'spinning-rev')">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#9664;&#9664;</div>
        <div class="btn-label">REW</div>
      </button>
      <button id="btn-r1" class="btn-t btn-play" disabled onclick="handleTransport(1, 'PLAY', 'spinning')">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#9654;</div>
        <div class="btn-label">PLAY</div>
      </button>
      <button id="btn-r5" class="btn-t btn-ff" disabled onclick="handleTransport(5, 'FF', 'spinning-fast')">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#9654;&#9654;</div>
        <div class="btn-label">FF</div>
      </button>

      <!-- ROW 2: RECORD, PAUSE, STOP -->
      <button id="btn-r3" class="btn-t btn-rec" disabled onclick="handleTransport(3, 'RECORD', 'spinning')">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#9679;</div>
        <div class="btn-label">RECORD</div>
      </button>
      <button id="btn-r4" class="btn-t btn-pause" disabled onclick="handleTransport(4, 'PAUSE', null)">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#10074;&#10074;</div>
        <div class="btn-label">PAUSE</div>
      </button>
      <button id="btn-r2" class="btn-t btn-stop" disabled onclick="handleTransport(2, 'STOP', null)">
        <div class="led-indicator"></div>
        <div class="btn-icon">&#9632;</div>
        <div class="btn-label">STOP</div>
      </button>
    </div>
  </div>
</div>

<div id="infoModal" class="app-modal" onclick="if(event.target===this) toggleInfoModal(false)">
  <div class="app-modal-content">
    <div class="modal-header">
      <h3 style="color:#38bdf8;font-size:16px;">Info</h3>
      <button class="modal-close" onclick="toggleInfoModal(false)">&times;</button>
    </div>
    <div class="info-list">
      <div class="info-row"><span class="info-label">Device</span><span class="info-val">AAIQ Relay Box Pico 2 W</span></div>
      <div class="info-row"><span class="info-label">Firmware</span><span class="info-val">v%s</span></div>
      <div class="info-row"><span class="info-label">App</span><span class="info-val">TAPE PWA</span></div>
    </div>
    <button class="btn-modal-action" onclick="toggleInfoModal(false)">Sluiten</button>
  </div>
</div>

<div id="iosModal" class="ios-modal" onclick="if(event.target===this) toggleIosModal(false)">
  <div class="ios-modal-content">
    <h3 id="iosModalTitle">Installatie op iPhone / iPad</h3>
    <div id="iosModalBody">
      <p>Open in Safari en kies Share &rarr; Add to Home Screen.</p>
    </div>
    <button onclick="toggleIosModal(false)">Begrepen</button>
  </div>
</div>

<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('btnInstall');
  if (btn) btn.style.display = 'inline-block';
});

function getIosBrowser() {
  const ua = navigator.userAgent || '';
  if (/FxiOS/i.test(ua)) return 'firefox';
  if (/CriOS/i.test(ua)) return 'chrome';
  if (/EdgiOS/i.test(ua)) return 'edge';
  if (/OPiOS/i.test(ua)) return 'opera';
  return 'safari';
}

function getBrowserEnv() {
  const ua = navigator.userAgent || '';
  const isIos = (/iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) && !window.MSStream;
  const isMac = /Macintosh|Mac OS X/i.test(ua) && !isIos;
  const isAndroid = /Android/i.test(ua);
  const isWindows = /Windows/i.test(ua);

  let browser = 'other';
  if (/FxiOS/i.test(ua)) browser = 'ios-firefox';
  else if (/CriOS/i.test(ua)) browser = 'ios-chrome';
  else if (/EdgiOS/i.test(ua)) browser = 'ios-edge';
  else if (/Firefox/i.test(ua)) browser = 'firefox';
  else if (/Edg/i.test(ua)) browser = 'edge';
  else if (/Chrome/i.test(ua)) browser = 'chrome';
  else if (/Safari/i.test(ua) && (isIos || isMac)) browser = 'safari';

  return { isIos, isMac, isAndroid, isWindows, browser };
}

function updateIosModalContent() {
  const titleEl = document.getElementById('iosModalTitle');
  const bodyEl = document.getElementById('iosModalBody');
  if (!bodyEl) return;

  const env = getBrowserEnv();
  if (env.isIos) {
    if (env.browser === 'ios-firefox') {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Firefox op iOS</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
        'Firefox op iOS ondersteunt PWA-installatie niet zoals Safari.<br>' +
        '1. Tik in Firefox op het menu (<b>&#8943;</b>).<br>' +
        '2. Kies <b>Openen in Safari</b>.<br>' +
        '3. Tik in Safari op de <b>Deel-knop</b> (Share) en kies <b>Zet op beginscherm</b> (+).</p>';
    } else if (env.browser === 'ios-chrome') {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Chrome op iOS</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
        'Chrome op iOS ondersteunt PWA-installatie niet zoals Safari.<br>' +
        '1. Tik op het <b>Deel-icoon</b> in de adresbalk of menu.<br>' +
        '2. Tik op <b>Zet op beginscherm</b> (of open in Safari &rarr; Deel &rarr; Zet op beginscherm).<br>' +
        '3. Tik op <b>Voeg toe</b>.</p>';
    } else if (env.browser === 'ios-edge' || /OPiOS/i.test(navigator.userAgent)) {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;color:#cbd5e1;">Deze browser op iOS ondersteunt PWA-installatie niet zoals Safari. Open deze pagina in Safari om TAPE aan het beginscherm toe te voegen.</p>';
    } else {
      if (titleEl) titleEl.textContent = 'Installatie op iPhone / iPad';
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Open in Safari en kies Share &rarr; Add to Home Screen.</p>' +
        '<p style="font-size:12px;color:#94a3b8;text-align:left;line-height:1.6;">' +
        '1. Tik op de <b>Deel-knop</b> (Share) in Safari.<br>' +
        '2. Scroll naar beneden en tik op <b>Zet op beginscherm</b> (+).<br>' +
        '3. Tik rechtsboven op <b>Voeg toe</b>.</p>';
    }
  } else if (env.isMac && env.browser === 'safari') {
    if (titleEl) titleEl.textContent = 'Installatie op Mac (Safari)';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Safari Web App op macOS</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      '1. Open het Safari-menu bovenaan.<br>' +
      '2. Kies <b>Archief &rarr; Voeg toe aan Dock...</b> (File &rarr; Add to Dock).<br>' +
      '3. Klik op <b>Voeg toe</b> om de app direct vanuit je Dock te openen.</p>';
  } else if (env.browser === 'firefox') {
    if (titleEl) titleEl.textContent = 'Web App op Firefox';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Firefox Desktop</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      'Firefox ondersteunt deze pagina direct als snelle Web App.<br>' +
      '• Druk op <b>Ctrl + D</b> om een bladwijzer te maken.<br>' +
      '• Of sleep het slot-icoontje uit de adresbalk naar je bureaublad.</p>';
  } else {
    if (titleEl) titleEl.textContent = 'App Installeren';
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">Web App Installatie</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' +
      '• <b>Chrome / Edge:</b> Klik op het installatie-icoontje (&#8853;) in de adresbalk.<br>' +
      '• <b>Mobiel:</b> Kies via het browsermenu <i>Toevoegen aan startscherm</i>.</p>';
  }
}

function promptInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
      deferredPrompt = null;
      const btn = document.getElementById('btnInstall');
      if (btn) btn.style.display = 'none';
    });
  } else {
    toggleIosModal(true);
  }
}

function toggleIosModal(show) {
  const m = document.getElementById('iosModal');
  if (m) {
    if (show) updateIosModalContent();
    m.style.display = show ? 'flex' : 'none';
  }
}

function toggleInfoModal(show) {
  const m = document.getElementById('infoModal');
  if (m) m.style.display = show ? 'flex' : 'none';
}

function toggleMenu(show) {
  const menu = document.getElementById('dropdownMenu');
  const btn = document.getElementById('btnMenu');
  if (!menu) return;
  const isVisible = menu.classList.contains('show');
  const next = show !== undefined ? show : !isVisible;
  if (next) {
    menu.classList.add('show');
    if (btn) btn.classList.add('active');
  } else {
    menu.classList.remove('show');
    if (btn) btn.classList.remove('active');
  }
}

function handleOutsideMenu(e) {
  const menuContainer = document.querySelector('.menu-container');
  if (menuContainer && !menuContainer.contains(e.target)) {
    toggleMenu(false);
  }
}
document.addEventListener('click', handleOutsideMenu);
document.addEventListener('touchstart', handleOutsideMenu, { passive: true });

const isIos = (/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) && !window.MSStream;
const isStandalone = window.navigator.standalone || window.matchMedia('(display-mode: standalone)').matches;
if (isIos && !isStandalone) {
  const btn = document.getElementById('btnInstall');
  if (btn) btn.style.display = 'inline-block';
}

let isPowered = false;
let isSending = false;
let currentMotion = null;
let activeTransport = null;

function updateTransportUI(activeName) {
  activeTransport = activeName;
  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (!btn) return;
    btn.classList.remove('active-fn');
    const led = btn.querySelector('.led-indicator');
    if (led) led.classList.remove('on');
  });

  if (activeName) {
    const map = {
      'PLAY': 'btn-r1',
      'STOP': 'btn-r2',
      'RECORD': 'btn-r3',
      'PAUSE': 'btn-r4',
      'FF': 'btn-r5',
      'REW': 'btn-r6'
    };
    const id = map[activeName];
    if (id) {
      const activeBtn = document.getElementById(id);
      if (activeBtn) {
        activeBtn.classList.add('active-fn');
        const activeLed = activeBtn.querySelector('.led-indicator');
        if (activeLed) activeLed.classList.add('on');
      }
    }
  }
}

function updatePowerUI(powered) {
  isPowered = !!powered;
  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (btn) btn.disabled = !isPowered;
  });

  const btnPower = document.getElementById('btnPower');
  if (btnPower) {
    if (isPowered) {
      btnPower.classList.remove('off');
      btnPower.classList.add('on');
    } else {
      btnPower.classList.remove('on');
      btnPower.classList.add('off');
      updateTransportUI(null);
      setReelsMotion(null);
    }
  }
}

async function togglePower() {
  if (isSending) return;
  const targetState = !isPowered;

  // Power OFF block: only allow Power OFF when STOP is active (or no transport active yet).
  // If PLAY, REW, FF, RECORD or PAUSE is active, refuse Power OFF.
  if (!targetState && activeTransport && activeTransport !== 'STOP') {
    console.warn('Power OFF blocked while transport function is active (' + activeTransport + ')');
    return;
  }

  isSending = true;
  try {
    const res = await fetch('/api/v1/relay/8', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({state: targetState})
    });
    if (res.ok) {
      const data = await res.json();
      const actualState = (data && data.state !== undefined) ? data.state : targetState;
      updatePowerUI(actualState);
    } else {
      checkInitialPower();
    }
  } catch(e) {
    console.error('Power API error:', e);
    checkInitialPower();
  } finally {
    isSending = false;
  }
}

async function checkInitialPower() {
  try {
    const res = await fetch('/api/v1/status', {cache: 'no-store'});
    if (res.ok) {
      const data = await res.json();
      const r8State = (data.relay && (data.relay[8] === 1 || data.relay['8'] === 1)) || (data.relay8 === true);
      updatePowerUI(!!r8State);
    }
  } catch(e) {
  }
}

function setReelsMotion(motionClass) {
  const left = document.getElementById('reelLeft');
  const right = document.getElementById('reelRight');
  if (left) left.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  if (right) right.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  currentMotion = motionClass;
}

async function handleTransport(relayNum, name, motion) {
  if (!isPowered || isSending) return;
  isSending = true;

  if (navigator.vibrate) {
    try { navigator.vibrate(35); } catch(e){}
  }

  const btn = document.getElementById('btn-r' + relayNum);
  if (btn) btn.classList.add('pressed');

  try {
    const res = await fetch('/api/v1/relay/' + relayNum + '/pulse', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({duration_ms: %d})
    });
    if (res.ok) {
      updateTransportUI(name);
      if (motion !== undefined) setReelsMotion(motion);
    }
  } catch(e) {
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove('pressed');
      isSending = false;
    }, 150);
  }
}

const GIT_LOGO_URL = 'https://raw.githubusercontent.com/ljvankempen/AAIQ-PWA-Assets/main/logo.png';
const LOGO_CACHE_KEY = 'aaiq_tape_logo_v1';

async function initLogo() {
  const logoImg = document.getElementById('headerLogo');
  if (!logoImg) return;

  function setLogoSrc(src) {
    if (src) logoImg.src = src;
  }

  // 1. Try to fetch the latest logo from Git raw URL
  try {
    const res = await fetch(GIT_LOGO_URL, { cache: 'no-cache' });
    if (res.ok) {
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = function() {
        const dataUrl = reader.result;
        try {
          localStorage.setItem(LOGO_CACHE_KEY, dataUrl);
        } catch(e) {}
        setLogoSrc(dataUrl);
      };
      reader.readAsDataURL(blob);
      return;
    }
  } catch(e) {
    // Git unreachable / offline
  }

  // 2. If Git fetch fails, try locally cached logo from localStorage
  try {
    const cached = localStorage.getItem(LOGO_CACHE_KEY);
    if (cached) {
      setLogoSrc(cached);
      return;
    }
  } catch(e) {}

  // 3. Fallback: if /logo.png fails too, hide image gracefully
  logoImg.onerror = function() {
    logoImg.style.display = 'none';
  };
}

window.addEventListener('DOMContentLoaded', () => {
  checkInitialPower();
  initLogo();
});
</script>
</body>
</html>""" % (
        FIRMWARE_VERSION,
        FIRMWARE_VERSION,
        config.pulse_ms(),
    )


def service_page(config, relay, wifi):
    states = relay.states()
    active = relay.active()
    waiting = relay.waiting()
    wifi_info = wifi.info()
    is_online = wifi_info.get("connected", False)

    rows = []
    for n in range(1, 9):
        st = states.get(n, 0)
        gpio = RELAY_PINS.get(n, 0)
        status_txt = "REST (LOW)"
        state_cls = "st-rest"
        if active and active.get("relay") == n:
            status_txt = "PULSE (%d ms)" % active.get("remaining_ms", 0)
            state_cls = "st-pulse"
        elif st == 1:
            status_txt = "ON (HIGH)"
            state_cls = "st-on"
        
        btn_controls = (
            '<button class="btn-ctrl btn-on" onclick="controlRelay(%d, true)" disabled>ON</button>'
            '<button class="btn-ctrl btn-off" onclick="controlRelay(%d, false)" disabled>OFF</button>'
            '<button class="btn-ctrl btn-pulse" onclick="controlRowPulse(%d)" disabled>PULSE</button>'
        ) % (n, n, n)

        rows.append(
            '<tr id="row-r%d">'
            '<td><b>R%d</b></td>'
            '<td>CH%d</td>'
            '<td>GP%d</td>'
            '<td><span id="st-r%d" class="badge-state %s">%s</span></td>'
            '<td style="width:110px"><input type="number" id="dur-r%d" value="100" min="1" max="10000" style="width:70px" disabled class="input-ctrl"> ms</td>'
            '<td class="actions">%s</td>'
            '</tr>' % (n, n, n, gpio, n, state_cls, status_txt, n, btn_controls)
        )

    relay_table_html = "".join(rows)
    free_ram_kb = (gc.mem_free() // 1024) if hasattr(gc, "mem_free") else 0
    uptime_sec = time.ticks_ms() // 1000
    uptime_str = "%dh %dm %ds" % (uptime_sec // 3600, (uptime_sec % 3600) // 60, uptime_sec % 60)

    header_text_block = (
        "=============================================================================\\n"
        "AAIQ RELAY BOX PICO 2 W\\n"
        "-----------------------------------------------------------------------------\\n"
        "File        : main.py\\n"
        "Version     : %s\\n"
        "Platform    : Raspberry Pi Pico 2 W / RP2350\\n"
        "Firmware    : MicroPython 1.29.0\\n"
        "Project     : AAIQ RELAY BOX PICO\\n"
        "-----------------------------------------------------------------------------\\n"
        "Relay mapping: R1=GP21 R2=GP20 R3=GP19 R4=GP18\\n"
        "               R5=GP17 R6=GP16 R7=GP15 R8=GP14\\n"
        "RGB LED WS2812: GP13\\n"
        "Active relay state: HIGH\\n"
        "Safe/rest state: LOW\\n"
        "Default pulse: %d ms\\n"
        "API version: %s\\n"
        "============================================================================="
    ) % (FIRMWARE_VERSION, config.pulse_ms(), API_VERSION)

    return """<!doctype html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AAIQ Relay Box - Diagnose & API Test Center</title>
<style>
body{font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:960px;margin:15px auto;padding:12px;background:#18181f;color:#e2e8f0;line-height:1.4}
.card{background:#23232d;padding:16px 20px;border-radius:8px;box-shadow:0 3px 10px rgba(0,0,0,0.35);margin-bottom:14px;border:1px solid #363645}
h1,h2,h3{margin-top:0;color:#fff}
h1{font-size:20px;border-bottom:1px solid #363645;padding-bottom:10px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
h2{font-size:15px;color:#00b4d8;margin-bottom:10px;border-bottom:1px solid #363645;padding-bottom:6px;display:flex;justify-content:space-between;align-items:center}
.badge-main{display:inline-block;padding:5px 12px;border-radius:14px;font-weight:bold;font-size:12px;letter-spacing:0.5px}
.online{background:#133926;color:#52b788;border:1px solid #2d6a4f}
.offline{background:#44141e;color:#f28482;border:1px solid #841c2c}
.badge-testmode{display:inline-block;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px}
.tests-off{background:#32323e;color:#a0aec0}
.tests-on{background:#670e17;color:#ff85a1;border:1px solid #c1121f;animation:pulseWarn 2s infinite}
@keyframes pulseWarn{0%%,100%%{opacity:1}50%%{opacity:0.75}}
.grid-status{display:grid;grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));gap:10px;font-size:13px}
.grid-item{background:#1c1c24;padding:8px 12px;border-radius:6px;border:1px solid #2f2f3d}
.grid-item b{color:#90e0ef}
table{width:100%%;border-collapse:collapse;margin:8px 0}
th,td{border:1px solid #363645;padding:8px 10px;text-align:left;font-size:13px}
th{background:#1c1c24;color:#94a3b8}
.badge-state{display:inline-block;padding:3px 8px;border-radius:4px;font-weight:bold;font-size:11px}
.st-rest{background:#2a333d;color:#94a3b8}
.st-on{background:#1b4332;color:#74c69d}
.st-pulse{background:#7f4f00;color:#ffd166}
button{cursor:pointer;font-family:inherit;font-size:12px;font-weight:bold;border-radius:4px;padding:6px 12px;border:none;transition:all 0.15s ease}
button:disabled{opacity:0.35;cursor:not-allowed}
.btn-ctrl{margin-right:4px;padding:4px 8px;font-size:11px}
.btn-on{background:#2d6a4f;color:#fff}.btn-on:hover:not(:disabled){background:#40916c}
.btn-off{background:#475569;color:#fff}.btn-off:hover:not(:disabled){background:#64748b}
.btn-pulse{background:#b07d10;color:#fff}.btn-pulse:hover:not(:disabled){background:#d49b20}
.btn-danger{background:#c1121f;color:#fff;padding:6px 14px;font-size:12px}.btn-danger:hover{background:#780000}
.btn-toggle{background:#0077b6;color:#fff;padding:6px 14px;font-size:12px}.btn-toggle:hover{background:#0096c7}
.btn-header{background:#334155;color:#e2e8f0;padding:5px 12px;font-size:12px;border:1px solid #475569}.btn-header:hover{background:#475569}
.btn-api{background:#2e3846;color:#e2e8f0;padding:6px 12px;font-size:12px;border:1px solid #475569}.btn-api:hover{background:#3b4759;color:#fff}
.tests-bar{display:flex;align-items:center;justify-content:space-between;background:#1c1c24;padding:10px 14px;border-radius:6px;margin-bottom:10px;border:1px solid #2f2f3d;flex-wrap:wrap;gap:8px}
.warn-banner{background:#3c280e;color:#ffd166;padding:8px 12px;border-radius:5px;margin-bottom:10px;border:1px solid #6b4700;font-size:12px}
select,input[type=number]{background:#18181f;border:1px solid #475569;color:#fff;padding:5px 8px;border-radius:4px;font-size:12px}
.api-table{width:100%%;margin-bottom:4px}
.api-table td{vertical-align:middle;padding:7px 10px}
.method-badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;margin-right:6px}
.m-get{background:#0d5c3a;color:#74c69d}
.m-post{background:#005082;color:#90e0ef}
.api-path{font-family:monospace;font-weight:bold;color:#f8fafc}
.api-result-box{background:#121217;border:1px solid #2f2f3d;border-radius:6px;padding:12px;margin-top:8px;font-family:monospace;font-size:12px}
.res-row{margin-bottom:5px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.res-label{color:#00b4d8;min-width:105px;font-weight:bold}
.status-code{font-weight:bold;padding:2px 6px;border-radius:3px}
.sc-200{background:#133926;color:#52b788}
.sc-err{background:#670e17;color:#ff85a1}
pre{background:#0d0d11;padding:10px;border-radius:4px;overflow-x:auto;color:#68d391;margin:6px 0 0;font-size:12px;border:1px solid #23232d}
.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);display:none;justify-content:center;align-items:center;z-index:999;padding:15px}
.modal-content{background:#23232d;border:1px solid #475569;border-radius:8px;max-width:760px;width:100%%;max-height:90vh;overflow-y:auto;padding:20px;box-shadow:0 8px 24px rgba(0,0,0,0.6)}
.modal-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #363645;padding-bottom:10px;margin-bottom:14px}
</style></head><body>

<div class="card">
<h1>
  <span>AAIQ Relay Box Pico 2 W &mdash; Diagnose &amp; Test Center</span>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <a href="/remote" class="btn-header" style="text-decoration:none;display:inline-flex;align-items:center;gap:5px;background:#0d5c3a;color:#74c69d;border-color:#2d6a4f">&#9654; TAPE Remote</a>
    <label style="display:inline-flex;align-items:center;gap:5px;font-size:12px;cursor:pointer;background:#1c1c24;padding:4px 10px;border-radius:4px;border:1px solid #363645">
      <input type="checkbox" id="chkAutoPoll" checked onchange="toggleAutoPoll()" style="margin:0;cursor:pointer">
      <span>Auto-Poll (1s)</span>
    </label>
    <button class="btn-header" onclick="toggleSourceModal(true)">&#8505; Firmware / Source Info</button>
    <span id="badgeOnline" class="badge-main %s">%s</span>
  </div>
</h1>
<div style="font-size:12px;color:#94a3b8">
  <b>Device ID:</b> <span id="valDeviceId">%s</span> &nbsp;|&nbsp;
  <b>Host:</b> <span id="valHostname">%s</span> &nbsp;|&nbsp;
  <b>Status Check:</b> <span id="valLastSeen">Connecting...</span>
</div>
</div>

<!-- 1. DEVICE STATUS -->
<div class="card">
<h2>1. Device Status</h2>
<div class="grid-status">
  <div class="grid-item"><b>Firmware:</b> %s</div>
  <div class="grid-item"><b>API Version:</b> %s (Driver 1.0)</div>
  <div class="grid-item"><b>IP Address:</b> <span id="valIp">%s</span></div>
  <div class="grid-item"><b>Wi-Fi SSID:</b> <span id="valSsid">%s</span></div>
  <div class="grid-item"><b>Platform:</b> RP2350 / Pico 2 W</div>
  <div class="grid-item"><b>HTTP API:</b> Port 80 (Active)</div>
  <div class="grid-item"><b>Default Pulse:</b> %d ms</div>
  <div class="grid-item"><b>Free RAM:</b> <span id="valRam">%d kB</span></div>
  <div class="grid-item"><b>Uptime:</b> <span id="valUptime">%s</span></div>
  <div class="grid-item"><b>Active Pulse:</b> <span id="valActive">%s</span></div>
</div>
</div>

<!-- 2. API FUNCTIONS (DRIVER SPECIFICATION V1.0) -->
<div class="card">
<h2>2. API Functions</h2>
<table class="api-table">
  <tr>
    <td style="width:38%%"><span class="method-badge m-get">GET</span> <span class="api-path">/api/v1/info</span></td>
    <td style="color:#94a3b8;font-size:12px">Device identity, firmware metadata &amp; relay count</td>
    <td style="text-align:right"><button class="btn-api" onclick="testApiGet('/api/v1/info')">Execute GET /info</button></td>
  </tr>
  <tr>
    <td><span class="method-badge m-get">GET</span> <span class="api-path">/api/v1/status</span></td>
    <td style="color:#94a3b8;font-size:12px">Live runtime status, relay states &amp; telemetry</td>
    <td style="text-align:right"><button class="btn-api" onclick="testApiGet('/api/v1/status')">Execute GET /status</button></td>
  </tr>
  <tr>
    <td><span class="method-badge m-post">POST</span> <span class="api-path">/api/v1/all/off</span></td>
    <td style="color:#94a3b8;font-size:12px">Emergency safe-state: switches all relays OFF</td>
    <td style="text-align:right"><button class="btn-api" onclick="testApiPost('/api/v1/all/off', {})">Execute POST /all/off</button></td>
  </tr>
  <tr>
    <td><span class="method-badge m-post">POST</span> <span class="api-path">/api/v1/relay/{n}</span></td>
    <td>
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <b>Relay:</b>
        <select id="apiRelaySelect1">
          <option value="1">R1</option><option value="2">R2</option>
          <option value="3">R3</option><option value="4">R4</option>
          <option value="5">R5</option><option value="6">R6</option>
          <option value="7">R7</option><option value="8">R8</option>
          <option value="9">R9 (Invalid)</option>
        </select>
        <b>State:</b>
        <select id="apiRelayState">
          <option value="true">ON (true)</option>
          <option value="false">OFF (false)</option>
        </select>
      </div>
    </td>
    <td style="text-align:right"><button class="btn-api" onclick="testApiRelayState()">Execute POST /relay/{n}</button></td>
  </tr>
  <tr>
    <td><span class="method-badge m-post">POST</span> <span class="api-path">/api/v1/relay/{n}/pulse</span></td>
    <td>
      <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <b>Relay:</b>
        <select id="apiRelaySelect2">
          <option value="1">R1</option><option value="2">R2</option>
          <option value="3">R3</option><option value="4">R4</option>
          <option value="5">R5</option><option value="6">R6</option>
          <option value="7">R7</option><option value="8">R8</option>
          <option value="9">R9 (Invalid)</option>
        </select>
        <b>Duration:</b>
        <input type="number" id="apiPulseDuration" value="100" min="-10" max="10000" style="width:65px"> ms
      </div>
    </td>
    <td style="text-align:right"><button class="btn-api" onclick="testApiRelayPulse()">Execute POST /relay/{n}/pulse</button></td>
  </tr>
</table>
</div>

<!-- 3. RELAY STATUS / TEST -->
<div class="card">
<h2>3. Relay Status / Test</h2>

<div id="readOnlyNotice" class="warn-banner">
  <b>Read-Only Mode:</b> Direct relay switching is locked. Enable Test Mode to perform manual relay operations.
</div>

<div class="tests-bar">
  <div>
    <b>Test Mode:</b>
    <span id="badgeTestMode" class="badge-testmode tests-off">DISABLED (Read-Only)</span>
  </div>
  <div>
    <button id="btnToggleTest" class="btn-toggle" onclick="toggleTestMode()">Enable Test Mode</button>
    <button class="btn-danger" onclick="executeAllOff()">ALL RELAYS OFF</button>
  </div>
</div>

<table>
<tr>
  <th>Relay</th>
  <th>Channel</th>
  <th>GPIO</th>
  <th>Current Status</th>
  <th>Pulse Duration</th>
  <th>Test Mode Actions</th>
</tr>
%s
</table>
</div>

<!-- 4. API RESULT -->
<div class="card">
<h2>4. API Result</h2>
<div class="api-result-box">
  <div class="res-row">
    <span class="res-label">HTTP Method:</span> <span id="resMethod" style="font-weight:bold">-</span> &nbsp;&nbsp;&nbsp;&nbsp;
    <span class="res-label" style="min-width:auto">Endpoint:</span> <span id="resEndpoint" style="color:#f8fafc">-</span>
  </div>
  <div class="res-row">
    <span class="res-label">HTTP Status:</span> <span id="resStatus" class="status-code">-</span> &nbsp;&nbsp;&nbsp;&nbsp;
    <span class="res-label" style="min-width:auto">Response Time:</span> <span id="resTime">-</span>
  </div>
  <div class="res-row" id="rowRequest">
    <span class="res-label">Request Body:</span> <span id="resRequest" style="color:#cbd5e1">-</span>
  </div>
  <div class="res-row" id="rowError" style="display:none;color:#ff85a1">
    <span class="res-label">Error Code:</span> <span id="resError" style="font-weight:bold">-</span>
  </div>
  <div class="res-row"><span class="res-label">JSON Response:</span></div>
  <pre id="resBody">Ready. Execute any API function or test action to evaluate response...</pre>
</div>
</div>

<!-- 5. FIRMWARE / SOURCE INFO MODAL -->
<div id="sourceModal" class="modal-overlay" onclick="if(event.target===this) toggleSourceModal(false)">
  <div class="modal-content">
    <div class="modal-head">
      <h3 style="margin:0;color:#00b4d8">&#8505; Firmware &amp; Source Header Information</h3>
      <button class="btn-header" onclick="toggleSourceModal(false)">&times; Close</button>
    </div>
    <div style="font-size:13px;margin-bottom:12px;color:#cbd5e1">
      Direct data extracted from the <code>src/main.py</code> single-file firmware source header:
    </div>
    <div class="grid-status" style="margin-bottom:14px">
      <div class="grid-item"><b>File:</b> main.py</div>
      <div class="grid-item"><b>Firmware Version:</b> %s</div>
      <div class="grid-item"><b>API Version:</b> %s (Driver 1.0)</div>
      <div class="grid-item"><b>Platform:</b> Raspberry Pi Pico 2 W / RP2350</div>
      <div class="grid-item"><b>Firmware Base:</b> MicroPython 1.29.0</div>
      <div class="grid-item"><b>Project:</b> AAIQ RELAY BOX PICO</div>
      <div class="grid-item"><b>Active State:</b> HIGH (Output 1)</div>
      <div class="grid-item"><b>Safe / Rest State:</b> LOW (Output 0)</div>
      <div class="grid-item"><b>Default Pulse:</b> %d ms</div>
      <div class="grid-item"><b>RGB LED WS2812:</b> GP13</div>
      <div class="grid-item"><b>Architecture:</b> Single Firmware File (main.py)</div>
    </div>
    <div style="font-size:12px;color:#94a3b8;margin-bottom:6px"><b>Raw Source Header (src/main.py):</b></div>
    <pre style="color:#90e0ef;font-size:11px">%s</pre>
    <div style="text-align:right;margin-top:14px">
      <button class="btn-toggle" onclick="toggleSourceModal(false)">Close</button>
    </div>
  </div>
</div>

<script>
let testMode = false;
let autoPollEnabled = true;
let isPolling = false;
let isCommandRunning = false;
let failedPolls = 0;
const MAX_FAILED_POLLS = 3;
let pollTimer = null;

function setControlsEnabled(enabled){
  document.querySelectorAll(".btn-ctrl").forEach(b => b.disabled = !enabled);
  document.querySelectorAll(".input-ctrl").forEach(i => i.disabled = !enabled);
  const badge = document.getElementById("badgeTestMode");
  const btnToggle = document.getElementById("btnToggleTest");
  const notice = document.getElementById("readOnlyNotice");
  if(enabled){
    badge.className = "badge-testmode tests-on";
    badge.textContent = "ENABLED (Test Mode Active)";
    btnToggle.className = "btn-danger";
    btnToggle.textContent = "Disable Test Mode";
    notice.style.display = "none";
  } else {
    badge.className = "badge-testmode tests-off";
    badge.textContent = "DISABLED (Read-Only)";
    btnToggle.className = "btn-toggle";
    btnToggle.textContent = "Enable Test Mode";
    notice.style.display = "block";
  }
}

function toggleTestMode(){
  testMode = !testMode;
  setControlsEnabled(testMode);
}

function toggleSourceModal(show){
  const modal = document.getElementById("sourceModal");
  modal.style.display = show ? "flex" : "none";
}

function toggleAutoPoll(){
  const chk = document.getElementById("chkAutoPoll");
  autoPollEnabled = chk ? chk.checked : true;
  if(autoPollEnabled){
    scheduleNextPoll(100);
  } else {
    if(pollTimer) clearTimeout(pollTimer);
    document.getElementById("valLastSeen").textContent = "Auto-Poll Paused (Manual Testing Mode)";
  }
}

function updateRelayUI(data){
  if(!data || !data.relay) return;
  for(let i=1; i<=8; i++){
    const stEl = document.getElementById("st-r" + i);
    if(!stEl) continue;
    if(data.active && data.active.relay === i){
      stEl.className = "badge-state st-pulse";
      stEl.textContent = "PULSE (" + (data.active.remaining_ms !== undefined ? data.active.remaining_ms : data.active.duration_ms) + " ms)";
    } else if(data.relay[i] === 1 || data.relay[String(i)] === 1 || data["relay" + i] === true){
      stEl.className = "badge-state st-on";
      stEl.textContent = "ON (HIGH)";
    } else {
      stEl.className = "badge-state st-rest";
      stEl.textContent = "REST (LOW)";
    }
  }
  if(data.active){
    const rem = data.active.remaining_ms !== undefined ? data.active.remaining_ms : data.active.duration_ms;
    document.getElementById("valActive").textContent = "R" + data.active.relay + " (" + data.active.duration_ms + " ms, rem: " + rem + " ms)";
  } else {
    document.getElementById("valActive").textContent = "None";
  }
  if(data.wifi && data.wifi.ip){
    document.getElementById("valIp").textContent = data.wifi.ip;
  }
  if(data.wifi && data.wifi.ssid){
    document.getElementById("valSsid").textContent = data.wifi.ssid;
  }
  if(data.free_ram_kb !== undefined){
    document.getElementById("valRam").textContent = data.free_ram_kb + " kB";
  }
  if(data.uptime_str){
    document.getElementById("valUptime").textContent = data.uptime_str;
  }
}

function scheduleNextPoll(delayMs){
  if(pollTimer) clearTimeout(pollTimer);
  if(!autoPollEnabled) return;
  pollTimer = setTimeout(pollStatus, delayMs !== undefined ? delayMs : 1000);
}

async function pollStatus(){
  if(!autoPollEnabled || isPolling || isCommandRunning) return;
  isPolling = true;
  const t0 = performance.now();
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutId = controller ? setTimeout(() => controller.abort(), 4500) : null;

  try{
    const fetchOptions = {cache: "no-store"};
    if(controller) fetchOptions.signal = controller.signal;
    const res = await fetch("/api/v1/status", fetchOptions);
    if(timeoutId) clearTimeout(timeoutId);

    if(res.ok){
      const data = await res.json();
      failedPolls = 0;
      updateRelayUI(data);
      const badge = document.getElementById("badgeOnline");
      badge.className = "badge-main online";
      badge.textContent = "ONLINE";
      const now = new Date();
      document.getElementById("valLastSeen").textContent = now.toLocaleTimeString() + " (" + Math.round(performance.now() - t0) + " ms)";
    } else {
      handlePollFailure();
    }
  }catch(e){
    if(timeoutId) clearTimeout(timeoutId);
    handlePollFailure();
  }finally{
    isPolling = false;
    if(autoPollEnabled && !isCommandRunning){
      scheduleNextPoll(1000);
    }
  }
}

function handlePollFailure(){
  if(!autoPollEnabled) return;
  failedPolls++;
  if(failedPolls >= MAX_FAILED_POLLS){
    markOffline();
  } else {
    const badge = document.getElementById("badgeOnline");
    if(badge.textContent === "ONLINE"){
      document.getElementById("valLastSeen").textContent = "Re-checking (" + failedPolls + "/" + MAX_FAILED_POLLS + ")...";
    }
  }
}

function markOffline(){
  const badge = document.getElementById("badgeOnline");
  badge.className = "badge-main offline";
  badge.textContent = "OFFLINE";
  document.getElementById("valLastSeen").textContent = "Connection Lost (" + new Date().toLocaleTimeString() + ")";
}

async function executeApiCall(method, endpoint, payload){
  isCommandRunning = true;
  if(pollTimer) clearTimeout(pollTimer);

  const t0 = performance.now();
  document.getElementById("resMethod").textContent = method;
  document.getElementById("resEndpoint").textContent = endpoint;
  document.getElementById("resRequest").textContent = payload ? JSON.stringify(payload) : "None";
  document.getElementById("rowError").style.display = "none";

  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timeoutId = controller ? setTimeout(() => controller.abort(), 5000) : null;

  try{
    const options = {
      method: method,
      headers: {"Content-Type": "application/json"}
    };
    if(controller) options.signal = controller.signal;
    if(payload && method !== "GET") options.body = JSON.stringify(payload);
    const res = await fetch(endpoint, options);
    if(timeoutId) clearTimeout(timeoutId);
    const elapsed = Math.round(performance.now() - t0);
    document.getElementById("resTime").textContent = elapsed + " ms";

    const stEl = document.getElementById("resStatus");
    stEl.textContent = res.status + " " + (res.statusText || (res.status === 200 ? "OK" : "Error"));
    stEl.className = "status-code " + (res.ok ? "sc-200" : "sc-err");

    const text = await res.text();
    let json = null;
    try { json = JSON.parse(text); } catch(e){}

    if(json){
      document.getElementById("resBody").textContent = JSON.stringify(json, null, 2);
      if(!res.ok || json.error){
        document.getElementById("rowError").style.display = "flex";
        document.getElementById("resError").textContent = json.error || ("HTTP " + res.status);
      } else {
        if(json.relay && json.state !== undefined){
          const stEl = document.getElementById("st-r" + json.relay);
          if(stEl){
            stEl.className = json.state ? "badge-state st-on" : "badge-state st-rest";
            stEl.textContent = json.state ? "ON (HIGH)" : "REST (LOW)";
          }
        } else if(json.relays_all_off){
          for(let i=1; i<=8; i++){
            const stEl = document.getElementById("st-r" + i);
            if(stEl){
              stEl.className = "badge-state st-rest";
              stEl.textContent = "REST (LOW)";
            }
          }
        }
      }
    } else {
      document.getElementById("resBody").textContent = text;
      if(!res.ok){
        document.getElementById("rowError").style.display = "flex";
        document.getElementById("resError").textContent = "HTTP Error " + res.status;
      }
    }
  }catch(e){
    if(timeoutId) clearTimeout(timeoutId);
    const elapsed = Math.round(performance.now() - t0);
    document.getElementById("resTime").textContent = elapsed + " ms";
    const stEl = document.getElementById("resStatus");
    stEl.textContent = "NETWORK ERROR";
    stEl.className = "status-code sc-err";
    document.getElementById("rowError").style.display = "flex";
    document.getElementById("resError").textContent = e.message || "Fetch failed";
    document.getElementById("resBody").textContent = "Request failed: " + e;
  }finally{
    isCommandRunning = false;
    if(autoPollEnabled){
      scheduleNextPoll(50);
    }
  }
}

function testApiGet(endpoint){
  executeApiCall("GET", endpoint, null);
}

function testApiPost(endpoint, payload){
  executeApiCall("POST", endpoint, payload);
}

function testApiRelayState(){
  const relay = document.getElementById("apiRelaySelect1").value;
  const stateStr = document.getElementById("apiRelayState").value;
  const state = stateStr === "true";
  executeApiCall("POST", "/api/v1/relay/" + relay, {state: state});
}

function testApiRelayPulse(){
  const relay = document.getElementById("apiRelaySelect2").value;
  const dur = parseInt(document.getElementById("apiPulseDuration").value, 10);
  executeApiCall("POST", "/api/v1/relay/" + relay + "/pulse", {duration_ms: dur});
}

function controlRelay(n, state){
  if(!testMode){
    alert("Relay control is only allowed in Test Mode.");
    return;
  }
  executeApiCall("POST", "/api/v1/relay/" + n, {state: state});
}

function controlRowPulse(n){
  if(!testMode){
    alert("Relay control is only allowed in Test Mode.");
    return;
  }
  const durInput = document.getElementById("dur-r" + n);
  const dur = durInput ? parseInt(durInput.value, 10) : 100;
  if(isNaN(dur) || dur <= 0){
    alert("Invalid pulse duration");
    return;
  }
  executeApiCall("POST", "/api/v1/relay/" + n + "/pulse", {duration_ms: dur});
}

function executeAllOff(){
  executeApiCall("POST", "/api/v1/all/off", {});
}

window.addEventListener("DOMContentLoaded", () => {
  setControlsEnabled(false);
  pollStatus();
});
</script>
</body></html>""" % (
        "online" if is_online else "offline",
        "ONLINE" if is_online else "OFFLINE",
        device_id(),
        hostname(),
        FIRMWARE_VERSION,
        API_VERSION,
        html_escape(wifi_info.get("ip", "None")),
        html_escape(wifi_info.get("ssid", "None")),
        config.pulse_ms(),
        free_ram_kb,
        uptime_str,
        html_escape(str(active)) if active else "None",
        relay_table_html,
        FIRMWARE_VERSION,
        API_VERSION,
        config.pulse_ms(),
        header_text_block,
    )


def parse_request(sock):
    t0 = time.ticks_ms()
    data = b""
    while time.ticks_diff(time.ticks_ms(), t0) < 3000:
        try:
            if hasattr(sock, "recv"):
                chunk = sock.recv(1024)
            elif hasattr(sock, "read"):
                chunk = sock.read(1024)
            else:
                chunk = sock.recv(1024)
            if not chunk:
                break
            data += chunk

            if b"\r\n\r\n" in data or b"\n\n" in data:
                break

            if len(data) > 8192:
                break
        except OSError as exc:
            err = getattr(exc, "args", [None])[0]
            if err in (11, 110) or "timed out" in str(exc).lower() or "eagain" in str(exc).lower() or "etimedout" in str(exc).lower():
                time.sleep_ms(2)
            else:
                break
        except Exception:
            break

    if not data or (b"\r\n\r\n" not in data and b"\n\n" not in data):
        return None

    try:
        text = data.decode("utf-8")
    except Exception:
        try:
            text = data.decode("latin1")
        except Exception:
            return None

    if "\r\n\r\n" in text:
        header, sep, body = text.partition("\r\n\r\n")
    else:
        header, sep, body = text.partition("\n\n")

    lines = header.split("\r\n") if "\r\n" in header else header.split("\n")
    first = lines[0].strip()
    parts = first.split(" ")
    if len(parts) < 2:
        return None

    method = parts[0].upper()
    path = parts[1]

    content_length = 0
    for line in lines[1:]:
        if line.lower().startswith("content-length:"):
            try:
                content_length = int(line.split(":", 1)[1].strip())
            except Exception:
                content_length = 0
            break

    # GET / HEAD / OPTIONS or Content-Length == 0: complete immediately
    if content_length == 0 or method in ("GET", "HEAD", "OPTIONS"):
        return method, path, ""

    body_bytes = body.encode("utf-8")
    if content_length > len(body_bytes):
        remaining = content_length - len(body_bytes)
        t_body_start = time.ticks_ms()
        while remaining > 0 and time.ticks_diff(time.ticks_ms(), t_body_start) < 2000:
            try:
                if hasattr(sock, "recv"):
                    chunk = sock.recv(min(1024, remaining))
                elif hasattr(sock, "read"):
                    chunk = sock.read(min(1024, remaining))
                else:
                    chunk = sock.recv(min(1024, remaining))
                if not chunk:
                    break
                data += chunk
                remaining -= len(chunk)
            except OSError as exc:
                err = getattr(exc, "args", [None])[0]
                if err in (11, 110) or "timed out" in str(exc).lower() or "eagain" in str(exc).lower() or "etimedout" in str(exc).lower():
                    time.sleep_ms(2)
                else:
                    break
            except Exception:
                break
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("latin1")
        if "\r\n\r\n" in text:
            header, sep, body = text.partition("\r\n\r\n")
        else:
            header, sep, body = text.partition("\n\n")

    return method, path, body

# Alias for backward compatibility
read_http_request = parse_request


class DNSCaptivePortal:
    def __init__(self):
        self.sock = None

    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", DNS_PORT))
            self.sock.settimeout(0.02)
            print("DNS Captive Portal: listening on port 53")
            return True
        except Exception as exc:
            print("DNS START ERROR:", exc)
            self.sock = None
            return False

    def update(self):
        if self.sock is None:
            return
        try:
            query, addr = self.sock.recvfrom(512)
        except Exception:
            return
        if len(query) < 12:
            return

        i = 12
        while i < len(query):
            length = query[i]
            i += 1
            if length == 0:
                break
            i += length
        if i + 4 > len(query):
            return

        question = query[12:i + 4]
        header = (
            query[:2] +
            b"\x81\x80" +
            b"\x00\x01" +
            b"\x00\x01" +
            b"\x00\x00" +
            b"\x00\x00"
        )
        answer = (
            b"\xc0\x0c" +
            b"\x00\x01" +
            b"\x00\x01" +
            b"\x00\x00\x00\x3c" +
            b"\x00\x04" +
            bytes([192, 168, 4, 1])
        )
        try:
            self.sock.sendto(header + question + answer, addr)
        except Exception:
            pass

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class HTTPServer:
    def __init__(self, config, relay, wifi, led=None):
        self.config = config
        self.relay = relay
        self.wifi = wifi
        self.led = led
        self.server = None
        self.restart_pending = False

    def start(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind(("0.0.0.0", HTTP_PORT))
            self.server.listen(5)
            self.server.setblocking(False)
            print("HTTP Server: listening on port 80 (Request-per-Request mode)")
            return True
        except Exception as exc:
            print("HTTP START ERROR:", exc)
            self.server = None
            return False

    def stop(self):
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
            self.server = None

    def update(self):
        if self.server is None:
            return

        client = None
        try:
            client, _ = self.server.accept()
        except OSError:
            return
        except Exception:
            return

        print("[HTTP] ACCEPT")
        try:
            try:
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            client.settimeout(3.0)
            req = parse_request(client)
            if req is None:
                return
            method, path, body = req
            print("[HTTP RX] %s %s" % (method, path))

            if self.wifi.setup_mode:
                if method == "POST" and path in ("/setup", "/setup/"):
                    form = parse_form(body)
                    ssid = form.get("ssid", "").strip()
                    password = form.get("password", "")
                    if not ssid:
                        res = response("<h1>SSID is required</h1>", "400 Bad Request")
                        send_response(client, res)
                        print("[HTTP TX] 400 %d bytes" % len(res))
                        return
                    if not self.config.set_wifi(ssid, password):
                        res = response("<h1>Save failed</h1>", "500 Internal Server Error")
                        send_response(client, res)
                        print("[HTTP TX] 500 %d bytes" % len(res))
                        return
                    self.relay.all_off()
                    self.restart_pending = True
                    res = response(
                        "<!doctype html><html><head><meta charset='utf-8'>"
                        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                        "<title>Saved</title></head><body style='font-family:Arial;padding:30px;text-align:center'>"
                        "<h2>Wi-Fi Credentials Saved</h2>"
                        "<p>Credentials encrypted and stored persistently.</p>"
                        "<p><b>The Relay Box is restarting...</b></p>"
                        "</body></html>"
                    )
                    send_response(client, res)
                    print("[HTTP TX] 200 %d bytes" % len(res))
                    return

                nets = scan_wifi_networks()
                res = response(setup_page(nets))
                send_response(client, res)
                print("[HTTP TX] 200 %d bytes" % len(res))
                return

            # Normal station mode: Serve HTTP API and Diagnose UI
            res_data = self.api_request(method, path, body)
            send_response(client, res_data)

            st_code = "200"
            if res_data and len(res_data) > 15:
                try:
                    first_line = res_data[:30].decode("latin1").split("\r\n")[0]
                    st_code = first_line.split(" ")[1]
                except Exception:
                    pass

            print("[HTTP TX] %s %d bytes" % (st_code, len(res_data)))
        except OSError as exc:
            err = getattr(exc, "args", [None])[0]
            if err not in (11, 110) and "timed out" not in str(exc).lower() and "eagain" not in str(exc).lower() and "etimedout" not in str(exc).lower():
                print("[HTTP ERROR] %s" % exc)
        except Exception as exc:
            print("[HTTP ERROR] %s" % exc)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
                print("[HTTP] CLOSE")

    def api_request(self, method, path, body=""):
        pure_path, _, query = path.partition("?")
        query_params = parse_form(query) if query else {}
        body_params = parse_body_dict(body) if body else {}

        # 1. Status Endpoint (high frequency polling)
        if method == "GET" and pure_path in ("/api/v1/status", "/api/v1/status/"):
            states = self.relay.states()
            active_info = self.relay.active()
            waiting_info = self.relay.waiting()
            wifi_info = self.wifi.info()
            is_wifi_conn = wifi_info.get("connected", False) if isinstance(wifi_info, dict) else False

            relays_desc = {}
            for i in range(1, 9):
                val = states.get(i, 0)
                if active_info and active_info.get("relay") == i:
                    relays_desc[str(i)] = "pulse"
                elif val == 1:
                    relays_desc[str(i)] = "on"
                else:
                    relays_desc[str(i)] = "rest"

            resp_data = {
                "success": True,
                "device_name": self.config.data.get("device_name", "AAIQ Relay Box Pico"),
                "device_id": device_id(),
                "hostname": hostname(),
                "firmware_version": FIRMWARE_VERSION,
                "api_version": API_VERSION,
                "wifi": wifi_info,
                "wifi_connected": is_wifi_conn,
                "relay": states,
                "relays": relays_desc,
                "active_relay": active_info.get("relay") if active_info else None,
                "remaining_ms": active_info.get("remaining_ms") if active_info else 0,
                "pulse": {"default_ms": self.config.pulse_ms()},
                "active": active_info,
                "waiting": waiting_info,
            }
            for i in range(1, 9):
                resp_data["relay%d" % i] = bool(states.get(i, 0))
            return response(resp_data)

        # 2. Info Endpoint
        if method == "GET" and pure_path in ("/api/v1/info", "/api/v1/info/"):
            return response({
                "success": True,
                "device": "AAIQ Relay Box Pico 2 W",
                "device_name": self.config.data.get("device_name", "AAIQ Relay Box Pico"),
                "device_id": device_id(),
                "hostname": hostname(),
                "platform": "Raspberry Pi Pico 2 W / RP2350",
                "firmware": FIRMWARE_VERSION,
                "firmware_version": FIRMWARE_VERSION,
                "api": "1.0",
                "api_version": API_VERSION,
                "relay_count": 8,
                "http": True,
                "https": False,
            })

        # 3. PR99 Remote PWA Page (Standard Startup Page)
        if method == "GET" and pure_path in ("/", "/remote", "/remote/", "/tape", "/tape/", "/pr99", "/pr99/"):
            html_page = pr99_remote_page(self.config, self.relay, self.wifi)
            return response(html_page)

        # 4. PWA Web App Manifest
        if method == "GET" and pure_path in ("/manifest.json", "/manifest.webmanifest"):
            return response(PWA_MANIFEST, "200 OK", "application/manifest+json")

        # 5. Service Worker
        if method == "GET" and pure_path == "/sw.js":
            return response(SW_JS, "200 OK", "application/javascript")

        # 6. PWA Icons
        if method == "GET" and pure_path == "/icon.svg":
            return response(ICON_SVG, "200 OK", "image/svg+xml")

        if method == "GET" and pure_path in ("/icon-192.png", "/icon-512.png"):
            return response(ICON_PNG_BYTES, "200 OK", "image/png")

        if method == "GET" and pure_path in ("/logo.png", "/logo", "/images/logo.png"):
            logo_data = get_logo_data()
            if logo_data:
                return response(logo_data, "200 OK", "image/png", extra="Cache-Control: public, max-age=86400")
            return response(b"", "404 Not Found", "text/plain")

        # 7. Diagnose / Service Page
        if method == "GET" and pure_path in ("/diagnose", "/diagnose/"):
            html_page = service_page(self.config, self.relay, self.wifi)
            return response(html_page)

        # 4. Relay Control & Fast Switching
        prefix = "/api/v1/relay/"
        if method == "POST" and pure_path.startswith(prefix):
            remainder = pure_path[len(prefix):]

            # Route: /api/v1/relay/{n}/on
            if remainder.endswith("/on"):
                try:
                    number = int(remainder[:-3])
                except Exception:
                    number = 0
                if self.relay.on(number):
                    if self.led:
                        self.led.flash_transport(number, 250)
                    print("[RELAY] R%d set ON" % number)
                    return response({"success": True, "relay": number, "state": 1})
                return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

            # Route: /api/v1/relay/{n}/off
            if remainder.endswith("/off"):
                try:
                    number = int(remainder[:-4])
                except Exception:
                    number = 0
                if self.relay.off(number):
                    if self.led:
                        self.led.flash_transport(number, 250)
                    print("[RELAY] R%d set OFF" % number)
                    return response({"success": True, "relay": number, "state": 0})
                return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

            # Route: /api/v1/relay/{n}/pulse
            if remainder.endswith("/pulse") or "/pulse" in remainder:
                number_text = remainder.split("/")[0]
                try:
                    number = int(number_text)
                except Exception:
                    number = 0

                if number not in self.relay.relays:
                    return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

                if "duration_ms" in body_params:
                    duration_val = body_params["duration_ms"]
                elif "duration" in body_params:
                    duration_val = body_params["duration"]
                elif "duration_ms" in query_params:
                    duration_val = query_params["duration_ms"]
                elif "duration" in query_params:
                    duration_val = query_params["duration"]
                else:
                    duration_val = self.config.pulse_ms()

                try:
                    duration_ms = int(duration_val)
                except Exception:
                    return response({"success": False, "error": "INVALID_DURATION"}, "400 Bad Request")

                if duration_ms <= 0:
                    return response({"success": False, "error": "INVALID_DURATION"}, "400 Bad Request")

                if self.relay.pulse(number, duration_ms):
                    if self.led:
                        self.led.flash_transport(number, duration_ms)
                    print("[RELAY] R%d PULSE for %d ms" % (number, duration_ms))
                    return response({
                        "success": True,
                        "relay": number,
                        "duration_ms": duration_ms,
                    })
                return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

            # Route: /api/v1/relay/{n} (with JSON/form body)
            try:
                number = int(remainder)
            except Exception:
                number = 0

            if number not in self.relay.relays:
                return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

            # Direct state change in body: {"state": true/false} (evaluated first for fastest switching)
            if "state" in body_params:
                st = body_params["state"]
                is_on = st is True or st == 1 or st == "1" or st == "true" or st == "on"
                if is_on:
                    self.relay.on(number)
                    if self.led:
                        self.led.flash_transport(number, 250)
                    print("[RELAY] R%d set ON" % number)
                    return response({"success": True, "relay": number, "state": True})
                else:
                    self.relay.off(number)
                    if self.led:
                        self.led.flash_transport(number, 250)
                    print("[RELAY] R%d set OFF" % number)
                    return response({"success": True, "relay": number, "state": False})

            # Pulse command in body
            if "duration_ms" in body_params or "duration" in body_params or "pulse" in body_params or body_params.get("action") == "pulse":
                if "duration_ms" in body_params:
                    dur_val = body_params["duration_ms"]
                elif "duration" in body_params:
                    dur_val = body_params["duration"]
                elif "pulse" in body_params and isinstance(body_params["pulse"], (int, str)):
                    dur_val = body_params["pulse"]
                else:
                    dur_val = self.config.pulse_ms()
                try:
                    duration_ms = int(dur_val)
                except Exception:
                    return response({"success": False, "error": "INVALID_DURATION"}, "400 Bad Request")
                if duration_ms <= 0:
                    return response({"success": False, "error": "INVALID_DURATION"}, "400 Bad Request")
                if self.relay.pulse(number, duration_ms):
                    if self.led:
                        self.led.flash_transport(number, duration_ms)
                    print("[RELAY] R%d PULSE for %d ms" % (number, duration_ms))
                    return response({"success": True, "relay": number, "duration_ms": duration_ms})
                return response({"success": False, "error": "INVALID_RELAY"}, "400 Bad Request")

            return response({"success": False, "error": "INVALID_REQUEST"}, "400 Bad Request")

        # 5. All Relays OFF
        if method == "POST" and pure_path in ("/api/v1/all/off", "/api/v1/all/off/"):
            self.relay.all_off()
            if self.led:
                self.led.flash(StatusLED.COLOR_BLUE, 250)
            print("[RELAY] ALL OFF (Emergency Safe State)")
            resp_data = {"success": True, "relays_all_off": True}
            for i in range(1, 9):
                resp_data["relay%d" % i] = False
            return response(resp_data)

        return response({"success": False, "error": "NOT_FOUND"}, "404 Not Found")


# Aliases for compatibility
HTTPSAPI = HTTPServer
HTTPAPI = HTTPServer


def configure_relay_default(relay, config):
    relay.set_default_duration_fn(config.pulse_ms)


def main():
    print("==============================================")
    print("AAIQ RELAY BOX PICO 2 W")
    print("Firmware:", FIRMWARE_VERSION)
    print("MicroPython: 1.29.0 / RP2350")
    print("RGB LED WS2812: GP13")
    print("==============================================")

    gc.collect()

    led = StatusLED(RGB_PIN)
    led.set_status("startup")

    relay = RelayController()
    relay.all_off()

    config = Config()
    configure_relay_default(relay, config)

    dns = DNSCaptivePortal()
    wifi = None
    http = None

    def on_mode_change(setup_mode):
        if setup_mode:
            if led:
                led.set_status("setup")
            dns.start()
        else:
            if led:
                led.set_status("online")
            dns.close()

    wifi = WiFiManager(config, relay, on_mode_change=on_mode_change, led=led)
    http = HTTPServer(config, relay, wifi, led=led)

    print("Device ID:", device_id())
    print("Hostname :", hostname())
    print("Setup AP :", wifi.setup_ap_name)

    wifi.start()

    if wifi.setup_mode:
        dns.start()
    http.start()

    try:
        watchdog = machine.WDT(timeout=WATCHDOG_TIMEOUT_MS) if machine and hasattr(machine, "WDT") else None
    except Exception as exc:
        print("WATCHDOG ERROR:", exc)
        watchdog = None

    last_gc = time.ticks_ms()
    while True:
        led.update()
        relay.update()
        wifi.update()

        if wifi.setup_mode:
            dns.update()
        http.update()

        if http.restart_pending:
            print("WIFI CONFIG SAVED - RESTARTING")
            relay.all_off()
            if led:
                led.set_status("startup")
            time.sleep_ms(500)
            if machine and hasattr(machine, "reset"):
                machine.reset()
            else:
                break

        if watchdog is not None:
            try:
                watchdog.feed()
            except Exception:
                pass

        now = time.ticks_ms()
        if time.ticks_diff(now, last_gc) >= 5000:
            gc.collect()
            last_gc = now

        time.sleep_ms(1)


if __name__ == "__main__":
    main()
