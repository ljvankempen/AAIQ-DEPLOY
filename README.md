# AAIQ-DEPLOY — Centrale Release & Deployment Repository

Welkom bij de officiële release- en deployment-repository van het **AAIQ Ecosysteem**. 

Deze repository fungeert uitsluitend als **Centraal Release- en Deployment-register** (**Single Source of Truth** voor deploybare artefacten).

---

## 1. Belangrijkste Uitgangspunten & Architectuur

1. **Uitsluitend Release- en Deployment-artefacten**:
   - `AAIQ-DEPLOY` is een geselecteerde release-output van de onderliggende development-repositories en workspaces.
   - De afzonderlijke development-repositories en workspaces blijven de exclusieve plaats voor volledige broncode, testsuites, testconfiguraties (`pytest.ini`) en ontwikkeldocumentatie.
   - Iedere release-directory (`vX.Y.Z/`) bevat **uitsluitend de bestanden die strikt noodzakelijk zijn om die specifieke versie te deployen of te runnen**.
   - Tests en development-documentatie horen **niet** thuis in de release-directories.

2. **AAIQ Studio als Enige Release-Publicist**:
   - **AAIQ Studio is de enige component die releases naar AAIQ-DEPLOY publiceert**.
   - Er wordt alleen een nieuwe release aangemaakt wanneer de gebruiker in AAIQ Studio **expliciet aangeeft dat er een nieuwe versie moet worden uitgebracht**.
   - Releases zijn **immutable** (onveranderlijk). Een eenmaal gepubliceerde versie wordt nooit achteraf gewijzigd; aanpassingen worden altijd als een nieuwe semantische versie (`vMAJOR.MINOR.PATCH`) uitgebracht.

3. **Deployment-orkestratie door AAIQ Studio**:
   - AAIQ Studio gebruikt de gevalideerde release-inhoud uit `AAIQ-DEPLOY` later voor geautomatiseerde uitrol naar hardware devices (zoals de Pico 2 W via OTA of USB) en cloud VPS instances.

4. **GitHub als Source of Truth voor Deploybare Releases**:
   - GitHub `AAIQ-DEPLOY` is het leidende register voor welke versies beschikbaar en gevalideerd zijn voor deployment.
   - Iedere deploybare component bezit een eigen, onafhankelijke versielevenscyclus (`vX.Y.Z`).

5. **Runtime Device Status vs. GitHub Source of Truth**:
   - De actuele firmwareversie en runtime-status van een fysiek apparaat (zoals de Pico 2 W Relay Box) wordt **nooit rechtstreeks door de PWA uit GitHub gelezen**.
   - De actuele status wordt altijd dynamisch opgevraagd via het apparaat zelf of via de TAPERC Gateway API (`GET /api/v1/info` / `GET /api/v1/status`).
   - GitHub levert uitsluitend de *beschikbare deploybare releaseversies*.

6. **Strikt Zero-Secrets & Veilige Productie-defaults**:
   - Cryptografische geheimen, private HMAC keys, API-tokens, database-credentials en Wi-Fi wachtwoorden worden **nooit in GitHub opgeslagen**.
   - Alle configuratiebestanden in release-mappen zijn `.example` sjablonen. Echte productiesleutels worden uitsluitend beheerd op de fysieke doelomgeving (VPS / device).

---

## 2. Repositorystructuur

```text
AAIQ-DEPLOY/
├── TAPE_REMOTE_BOX/
│   ├── firmware/
│   │   └── v0.4.24/                   # Alleen benodigde firmware runtime/deployment files
│   │       ├── config.json            # Apparaatconfiguratie template
│   │       └── src/
│   │           └── main.py            # MicroPython runtime firmware voor RP2350
│   ├── pwa/
│   │   └── v1.0.0/                    # Alleen benodigde PWA files
│   │       ├── css/
│   │       │   └── style.css          # Studio Dark Slate styling
│   │       ├── images/                # PWA iconen, logo's en grafische assets
│   │       ├── js/
│   │       │   └── app.js             # Client logica en gateway communicatie
│   │       ├── index.html             # Single-page PWA UI
│   │       ├── manifest.json          # Web App Manifest
│   │       └── sw.js                  # Service Worker voor asset caching
│   ├── gateway/
│   │   └── v1.0.0/                    # Alleen benodigde gateway runtime/deployment files
│   │       ├── caddy/
│   │       │   └── Caddyfile.example  # Reverse-proxy template
│   │       ├── config/
│   │       │   ├── config.example.json
│   │       │   └── secrets.example.json
│   │       ├── src/                   # Python aiohttp gateway backend modules
│   │       ├── systemd/
│   │       │   └── taperc-gateway.service # Systemd service unit template
│   │       ├── .env.example           # Omgevingsvariabelen template
│   │       └── requirements.txt       # Productie Python dependencies
│   └── deploy/                        # VPS deployment-, update- en recoverytooling
│       ├── caddy/
│       │   └── Caddyfile.example
│       ├── systemd/
│       │   └── taperc-gateway.service
│       ├── deploy.sh                  # Geautomatiseerde VPS lifecycle CLI
│       ├── README.md
│       └── TAPERC_VPS_Deployment_and_Recovery.md
│
├── APP/
│   ├── profile/
│   │   └── v0.1.0/                    # APP Device Profile release
│   ├── remote/
│   │   └── v0.1.0/                    # APP Dynamic Remote Screen release
│   └── deploy/                        # Toekomstige APP deployment scripts
│       └── README.md
│
└── README.md                          # Centrale deployment repository documentatie
```

---

## 3. Vastgestelde Releaseversies

| Component | Huidige Release | Doelplatform | Runtime / Technologie | Release Pad |
|---|---|---|---|---|
| **TAPE Remote Box Firmware** | `v0.4.24` | Raspberry Pi Pico 2 W (RP2350) | MicroPython 1.29.0 | `TAPE_REMOTE_BOX/firmware/v0.4.24/` |
| **TAPE Remote PWA** | `v1.0.0` | Browsers (iOS / Android / Desktop) | HTML5 / CSS3 / ES6 / PWA | `TAPE_REMOTE_BOX/pwa/v1.0.0/` |
| **TAPERC Public Gateway** | `v1.0.0` | Linux VPS (`/opt/aaiq/taperc/`) | Python 3.10+ / aiohttp / Caddy | `TAPE_REMOTE_BOX/gateway/v1.0.0/` |
| **AAIQ APP Profile** | `v0.1.0` *(draft)* | AAIQ Studio / Cloud Registry | JSON Schema / Profile Spec | `APP/profile/v0.1.0/` |
| **AAIQ APP Remote Screens** | `v0.1.0` *(draft)* | AAIQ Studio / Client UI | Dynamic Screen Definitions | `APP/remote/v0.1.0/` |

---

## 4. Release- en Deploymentflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Development Workspaces                          │
│               (Broncode, Unit Tests, Pytest, Dev Docs)                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Expliciete gebruikersopdracht in Studio:
                                    │ "Publiceer nieuwe release"
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        AAIQ Studio Orchestrator                        │
│            (Valideert versienummer, bouwt release bundle,              │
│                 verwijdert dev/test files & publiceert)                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Git Push (Immutable Release)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   GitHub: AAIQ-DEPLOY (Release Repo)                   │
│                      (Single Source of Truth)                          │
│   ├── TAPE_REMOTE_BOX/firmware/vX.Y.Z/                                 │
│   ├── TAPE_REMOTE_BOX/pwa/vX.Y.Z/                                      │
│   ├── TAPE_REMOTE_BOX/gateway/vX.Y.Z/                                  │
│   └── APP/{profile,remote}/vX.Y.Z/                                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Georkestreerde deployment
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Productie Doelomgevingen                       │
│  - Raspberry Pi Pico 2 W (MicroPython firmware flash via OTA/USB)      │
│  - Linux VPS (/opt/aaiq/taperc/public-taperc/ via deploy.sh)          │
│  - PWA Web Hosting (HTTPS taperc.aaiq.nl)                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. VPS Gateway Deployment (`deploy/deploy.sh`)

Voor het uitrollen van de gateway-release op de Linux VPS (`/opt/aaiq/taperc/public-taperc/`) wordt gebruikgemaakt van de tooling onder `TAPE_REMOTE_BOX/deploy/`:

```bash
# Eerste installatie (idempotent, stelt rechten in onder user aaiq)
sudo ./deploy.sh install

# Veilige update met geautomatiseerde pre-backup en auto-rollback bij falen
sudo ./deploy.sh update

# Systeemgezondheid controleren (lokaal en via publieke HTTPS health check)
sudo ./deploy.sh health

# Rollback naar eerdere backup
sudo ./deploy.sh rollback
```
