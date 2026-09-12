# AAIQ — TAPE_REMOTE_BOX Subproject

Het **TAPE_REMOTE_BOX** subsysteem omvat de volledige end-to-end architectuur voor de fysieke besturing van analoge bandrecorders (zoals de Revox PR99 en Revox B77) via de AAIQ Relay Box Pico 2 W, de standalone TAPE PWA en de TAPERC Public Gateway.

---

## 1. Structuur & Modules

```text
TAPE_REMOTE_BOX/
├── firmware/       # Pico 2 W MicroPython 1.29.0 firmware (main.py, hardware relay logic, tests)
├── pwa/            # Standalone TAPE Remote Progressive Web App (HTML/CSS/JS, Service Worker, assets)
├── gateway/        # Asynchrone TAPERC Public Gateway service (AIOHTTP, HMAC auth, unit- & integratietests)
└── deploy/         # Geautomatiseerde VPS deployment, backup, update en recovery tooling (deploy.sh)
```

---

## 2. Overzicht per Component

### 1. `firmware/`
- Draait direct op de **Raspberry Pi Pico 2 W (RP2350)** microcontroller.
- Schakelt 8 hardware-relais met een standaard pulsduur van 100 ms.
- Biedt mechanische interlock (beveiliging tegen conflicterende commando's en veilige power-down blokkade).
- Bevat veilige Wi-Fi provisioning via Captive Portal met hardware-gebonden AES-128 encryptie van credentials.

### 2. `pwa/`
- Responsive, standalone Progressive Web App met studio dark theme.
- Visuele dual-reel animatie gesynchroniseerd met transporttoestanden (`REW`, `PLAY`, `FF`, `REC`, `PAUSE`, `STOP`).
- Tactiele feedback (`vibrate`), Power-toggle interlock en cross-platform installatie-ondersteuning (iOS Safari, Android Chrome, macOS Safari).
- Service Worker caching met strikte pass-through voor realtime `/api/*` commando's.

### 3. `gateway/`
- Asynchrone cloud gateway (`https://taperc.aaiq.nl`) geschreven in Python 3 / AIOHTTP.
- Maakt veilige besturing mogelijk over het publieke internet zonder inkomende poortdoorsturing op het lokale studio-netwerk (outbound WebSocket `wss://taperc.aaiq.nl/device/connect`).
- Cryptografische HMAC-SHA256 challenge-response authenticatie met single-use nonces tegen replay-aanvallen.
- Volledige scheiding tussen device registry en secrets store.
- Ondersteunt zowel Fase-1 default-device routes (`/api/v1/relay/...`) als multi-device endpoints (`/api/v1/device/{device_id}/...`).

### 4. `deploy/`
- Beheert de VPS deployment onder Linux-user `aaiq` op `/opt/aaiq/taperc/public-taperc/`.
- Biedt idempotente installatie, automatische pre-backups, integratietests en automatische rollback bij fouten via `deploy.sh`.
- Bevat geharde systemd unit templates en Caddy reverse-proxy definities.
