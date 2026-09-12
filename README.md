<<<<<<< HEAD
# AAIQ-PWA-Assets
Public assets voor AAIQ oa images
=======
# AAIQ-DEPLOY — Centrale Deployment Repository

**AAIQ-DEPLOY** is de centrale en gezaghebbende deployment repository voor het complete AAIQ ecosysteem. Deze repository brengt alle componenten (microcontroller firmware, progressive web apps, cloud gateways en toekomstige applicatiemodules) samen in één overzichtelijke, reproduceerbare en geautomatiseerde structuur.

---

## 1. Doel & Scope van AAIQ-DEPLOY

- **Centrale Bron van Waarheid**: Uniforme opslag en versionering van alle implementaties en deployment-artefacten.
- **Reproduceerbaarheid**: Idempotente installatie, updates, automatische pre-backups en faalveilige rollbacks voor zowel cloud/VPS gateways als randapparatuur.
- **Modulaire Architectuur**: Duidelijke isolatie tussen embedded hardware-besturing (`TAPE_REMOTE_BOX`), client software (`APP`), en centrale cloud-diensten (`gateway`).
- **Geen Productie-Secrets in Git**: Strikte handhaving van een gescheiden secrets store; configuratiebestanden in de repository bevatten uitsluitend sjablonen en metadata.

---

## 2. Rol van GitHub & AAIQ Studio

### GitHub als Source of Truth
- Alle code, firmwarebronbestanden, PWA assets, testsuites en deploymentscripts worden beheerd via Git op GitHub.
- Releases worden voorzien van semantische tags (`vX.Y.Z`).
- Pull requests en CI-pipelines valideren wijzigingen automatisch via unit- en integratietests vóór samenvoeging.

### AAIQ Studio als Toekomstige Centrale Deployment-Orchestrator
- **AAIQ Studio** zal fungeren als het centrale commandocenter voor studiobeheer.
- Vanuit AAIQ Studio kunnen apparaten worden geprovisioneerd, profielen worden gesynchroniseerd, firmware-updates worden geïnitieerd en gateways worden gemonitord.
- AAIQ Studio orchestreert de flow tussen GitHub releases, VPS gateway services en de fysieke studio-hardware.

---

## 3. Repositorystructuur

```text
AAIQ-DEPLOY/
├── TAPE_REMOTE_BOX/
│   ├── firmware/               # Pico 2 W MicroPython 1.29.0 firmware, hardware drivers & tests
│   │   ├── config.json         # Voorbeeld hardware configuratie
│   │   ├── src/                # Firmware broncode (main.py)
│   │   ├── tests/              # 33 pytest unit- & integratietests
│   │   └── README.md           # Firmware documentatie & GPIO pin mapping
│   ├── pwa/                    # Standalone TAPE Remote Progressive Web App
│   │   ├── css/                # Studio Dark Slate styling & reel animaties
│   │   ├── images/             # Iconen, logo's en SVG deck vector graphics
│   │   ├── js/                 # Client applicatielogica, REST API & status polling
│   │   ├── index.html          # Hoofdpagina PWA
│   │   ├── manifest.json       # Web App Manifest
│   │   ├── sw.js               # Service Worker met cache lifecycle management
│   │   └── README.md           # PWA architectuur & installatiehandleiding
│   ├── gateway/                # TAPERC Public Gateway service
│   │   ├── caddy/              # Caddy 2 reverse proxy configuratievoorbeelden
│   │   ├── config/             # Metadata registry & secrets store templates
│   │   ├── src/                # Asynchrone gateway code (AIOHTTP, HMAC auth, sessies)
│   │   ├── systemd/            # Systemd service unit template
│   │   ├── tests/              # 34 pytest unit- & WebSocket integratietests
│   │   ├── .env.example        # Voorbeeld omgevingsvariabelen
│   │   ├── requirements.txt    # Python runtime dependencies
│   │   └── README.md           # Gateway documentatie & API specificaties
│   ├── deploy/                 # Geautomatiseerde VPS deployment, backup & recovery
│   │   ├── caddy/              # Reverse proxy templates
│   │   ├── systemd/            # Systemd service templates
│   │   ├── deploy.sh           # Geautomatiseerd install-, update-, backup- & rollback-script
│   │   ├── TAPERC_VPS_Deployment_and_Recovery.md # Volledige VPS handleiding
│   │   └── README.md           # Deployment quick start
│   └── README.md               # TAPE_REMOTE_BOX subproject overzicht
├── APP/
│   ├── profile/                # Gebruikersprofielen, presets en machine-configuraties
│   │   └── README.md
│   ├── remote/                 # Multi-device remote besturing & telemetrie
│   │   └── README.md
│   ├── deploy/                 # APP deployment tooling & pipelines
│   │   └── README.md
│   └── README.md               # APP subproject overzicht
└── README.md                   # Deze repository-hoofddocumentatie
```

---

## 4. Subprojecten in Detail

### A. TAPE_REMOTE_BOX
Het subsysteem voor professionele relaissturing van tapedecks (zoals de Revox PR99 en Revox B77):
- **`firmware/`**: Draait op de Raspberry Pi Pico 2 W (RP2350). Schakelt 8 relais met mechanische interlock, DNS captive portal setup en hardware-gebonden AES-128 encryptie van Wi-Fi credentials.
- **`pwa/`**: Standalone Progressive Web App met visuele dual-reel weergave, transportschakeling (`REW`, `PLAY`, `FF`, `REC`, `PAUSE`, `STOP`), haptische feedback en veilige Power-down blokkade.
- **`gateway/`**: TAPERC Public Gateway (`https://taperc.aaiq.nl`) op poort 8080 achter Caddy. Handelt uitgaande device-WebSockets af (`wss://taperc.aaiq.nl/device/connect`), waardoor geen poortforwarding op de studio-locatie nodig is.
- **`deploy/`**: Beheert de VPS deployment onder Linux-user `aaiq` op `/opt/aaiq/taperc/public-taperc/` met `deploy.sh`.

### B. APP (Toekomstig)
Gereserveerde, aantoonbare structuur voor toekomstige studio-applicaties:
- **`profile/`**: Beheer van deck-specifieke parameters, audio-routeringspresets en gebruikersrechten.
- **`remote/`**: Gecombineerde bedieningsinterface voor meerdere studio-apparaten gelijktijdig.
- **`deploy/`**: Geautomatiseerde release- en distributietools voor desktop- en mobiele AAIQ APP clients.

---

## 5. Release- en Versiebeheer

- **Semantische Versienummering**: Releases volgen `MAJOR.MINOR.PATCH` (bijv. `v0.4.24` voor firmware, `v1.0.0` voor gateway en PWA).
- **Consistente Metadata**: Versienummers worden synchroon bijgewerkt in de code (`FIRMWARE_VERSION`, `sw.js` cache-tags, `src/__init__.py`).
- **Release Artifacts**: Bij elke release worden getagde tarball-archieven en firmware-images gegenereerd.

---

## 6. Deployment, Backup en Rollback

Het script `TAPE_REMOTE_BOX/deploy/deploy.sh` biedt een complete, idempotente workflow:

| Commando | Beschrijving |
|---|---|
| `sudo ./deploy.sh install` | Voert een volledige initiële installatie uit (user, mappen, venv, deps, service, Caddy validatie). |
| `sudo ./deploy.sh update` | Maakt automatisch een pre-backup in `/opt/aaiq/taperc/backups/`, updatet code, valideert tests, herstart service en voert bij falen direct een **automatische rollback** uit. |
| `sudo ./deploy.sh backup` | Maakt een handmatige gecomprimeerde backup van de runtime-omgeving. |
| `sudo ./deploy.sh rollback [bestand]` | Herstelt de meest recente of een specifiek opgegeven backup en heractiveert de daemon. |
| `sudo ./deploy.sh health` | Controleert systemd status, poort 8080 listener, lokale health checks en publieke HTTPS endpoints. |
| `sudo ./deploy.sh test` | Voert de volledige geautomatiseerde testsuite uit binnen de venv. |

---

## 7. PWA Caching & Versioning

- **Strikte Service Worker Isolatie**: De Service Worker (`sw.js`) beheert statische assets (`/`, `/remote`, `/index.html`, `/css/style.css`, `/js/app.js`, `/manifest.json`, `/images/*`).
- **Geen API Caching**: Aanroepen naar `/api/*` worden direct doorgestuurd naar het netwerk en **nooit gecachet**.
- **Naadloze Cache Busting**: Bij een nieuwe deployment wordt `CACHE_NAME` (`tape-remote-vX.Y.Z`) verhoogd; de Service Worker schoont verouderde caches direct op bij activatie (`self.clients.claim()`).
- **Dynamic Asset Fallback**: Merklogo's worden dynamisch gesynchroniseerd met GitHub raw assets met persistente fallback naar localStorage.

---

## 8. Security & Secrets Architectuur

1. **Geen Plaintext Secrets in Repository**:
   - `config.example.json` en `.env.example` bevatten uitsluitend configuratievoorbeelden en dummy-sleutels.
   - Echte HMAC-sleutels worden op de productieserver handmatig geplaatst in `/opt/aaiq/taperc/public-taperc/config/secrets.json` of via environment variabelen (`TAPERC_SECRET_<ID>`).
2. **Strikte Scheiding van Device Registry & Secrets Store**:
   - De registry (`config.json`) bevat alleen publieke apparaat-metadata (`device_id`, `name`, `secret_id`, `relay_count`).
   - De secrets store (`secrets.json`) bevat de cryptografische sleutels per `secret_id` en is beveiligd met bestandsrechten `chmod 600` (alleen leesbaar voor user `aaiq`).
3. **HMAC-SHA256 Challenge-Response Handshake**:
   - Bij het openen van `wss://taperc.aaiq.nl/device/connect` genereert de gateway een cryptografisch willekeurige 32-byte nonce.
   - De Pico ondertekent de nonce met `HMAC-SHA256(secret_key, nonce)`.
   - De nonce is single-use en vervalt na 60 seconden; constante-tijd stringvergelijking (`hmac.compare_digest`) voorkomt timing-aanvallen.
4. **Linux Systeemsandboxing**:
   - De gateway-daemon draait onder de ongeprivilegieerde gebruiker `aaiq` met `ProtectSystem=full`, `ProtectHome=true` en `NoNewPrivileges=true`.

---

## 9. Scheiding van TAPERC en AAIQ Suite

- **Volledige Functionele & Technische Scheiding**: De TAPERC Gateway en de TAPE Remote Box opereren 100% autonoom en hebben geen directe afhankelijkheden van de interne AAIQ Suite code.
- **Gestandaardiseerde REST & WebSocket Contracten**: Communicatie verloopt uitsluitend via de gedocumenteerde `/api/v1/...` routes en WebSocket protocollen.
- **Geen Interferentie**: Wijzigingen in TAPERC laten bestaande AAIQ Suite componenten en Caddy-configuraties volledig intact.

---

## 10. Toekomstige GitHub $\rightarrow$ VPS/Device Deploymentflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          GitHub Repository                             │
│                  AAIQ-DEPLOY (Source of Truth)                         │
│     - Firmware Tags (v0.4.x)       - Gateway Releases (v1.0.x)         │
│     - PWA Static Assets             - Automated CI/CD Workflows         │
└───────────────────┬───────────────────────────────────┬────────────────┘
                    │ Release Webhook / Action          │ OTA Firmware Push
                    ▼                                   ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│             Linux VPS                │  │    Studio Relay Box (Pico)   │
│       https://taperc.aaiq.nl         │  │     Hardware Relais Node     │
│   - deploy.sh automated update       │  │   - MicroPython Runtime      │
│   - Pre-backup & Health Validation   │  │   - Outbound WebSocket WSS   │
│   - Caddy 2 Reverse Proxy (TLS)      │  │   - Local Web Fallback       │
└──────────────────────────────────────┘  └──────────────────────────────┘
                    ▲                                   ▲
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   │             AAIQ Studio             │
                   │    (Centrale Deployment Orchestrator)│
                   └─────────────────────────────────────┘
```

---

## 11. Testen & Verificatie

Voer de geautomatiseerde testsuites uit voor alle onderdelen:

```bash
# Firmware testsuite (33 tests)
python -m pytest TAPE_REMOTE_BOX/firmware/tests/ -v

# Gateway testsuite (34 tests)
python -m pytest TAPE_REMOTE_BOX/gateway/tests/ -v
```
>>>>>>> b149ba6 (Structure AAIQ-DEPLOY as central versioned release repository)
