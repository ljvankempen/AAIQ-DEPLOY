# AAIQ TAPE Remote Box — Pico 2 W Firmware

Dit onderdeel bevat de complete MicroPython 1.29.0 firmware voor de **AAIQ Relay Box Pico 2 W** (RP2350 microcontroller), ontworpen voor professionele relaissturing van tapedecks (zoals de Revox PR99 en B77).

---

## 1. Specificaties & Hardware Mapping

- **Platform**: Raspberry Pi Pico 2 W (RP2350)
- **Firmwareversie**: v0.4.24
- **Runtime**: MicroPython 1.29.0
- **API Versie**: v1 (`/api/v1/...`)
- **Standaard Pulsduur**: 100 ms

### GPIO Pin Mapping
| Relais | Pin (RP2350) | Functie (Revox PR99) | Actieve Toestand | Ruststand |
|---|---|---|---|---|
| **R1** | `GP21` | PLAY | HIGH (3.3V) | LOW (0V) |
| **R2** | `GP20` | STOP | HIGH (3.3V) | LOW (0V) |
| **R3** | `GP19` | RECORD | HIGH (3.3V) | LOW (0V) |
| **R4** | `GP18` | PAUSE | HIGH (3.3V) | LOW (0V) |
| **R5** | `GP17` | FAST FORWARD (FF) | HIGH (3.3V) | LOW (0V) |
| **R6** | `GP16` | REWIND (REW) | HIGH (3.3V) | LOW (0V) |
| **R7** | `GP15` | RESERVE | HIGH (3.3V) | LOW (0V) |
| **R8** | `GP14` | POWER (Deck Main Power) | HIGH (3.3V) | LOW (0V) |
| **RGB** | `GP13` | WS2812 Status LED | NeoPixel RGB | - |

---

## 2. Architectuur & Functionaliteit

1. **Non-blocking Asynchrone HTTP Server**:
   - Afhandeling van REST API commando's (`/api/v1/relay/{n}`, `/api/v1/relay/{n}/pulse`, `/api/v1/status`, `/api/v1/all/off`).
   - Lage latency (<10ms) relais- en pulsactivatie.
   - Mechanische interlock (beveiliging tegen gelijktijdige conflicterende transportcommando's en veilige power-down blokkade tijdens transport).

2. **Wi-Fi Provisioning & Captive Portal**:
   - Automatische fallback naar AP-modus (`AAIQ-Relay-Setup-XXXXXX`) en DNS captive portal indien geen Wi-Fi geconfigureerd is.
   - Hardware-gebonden AES-128 encryptie van Wi-Fi inloggegevens met `machine.unique_id()`.

3. **Status & Diagnose UI**:
   - Embedded TAPE Remote PWA interface op `/remote` en `/`.
   - Real-time telemetrie en handmatig testcentrum op `/diagnose`.

---

## 3. Bestandsstructuur

```text
firmware/
├── config.json             # Apparaatconfiguratie template
├── src/
│   └── main.py             # Volledige MicroPython firmware
├── tests/
│   ├── test_gateway_routing.py     # Routering en MIME types
│   ├── test_pwa_crossplatform.py   # Cross-platform PWA compatibiliteit
│   ├── test_relay.py               # Basis relaislogica
│   ├── test_relay_box.py           # Uitgebreide testsuite (33 tests)
│   └── test_relay_sequential.py    # Sequentiële pulsvalidatie
└── README.md               # Deze documentatie
```

---

## 4. Tests Uitvoeren

De unit- en integratietests kunnen direct worden uitgevoerd via pytest:

```bash
python -m pytest tests/ -v
```
