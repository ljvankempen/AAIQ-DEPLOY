# TAPERC Public Gateway (Fase-1)

De **TAPERC Public Gateway** is een asynchrone cloud/VPS gateway-service voor **AAIQ TAPE Remote Control (TAPERC)**. De gateway stelt webclients (zoals de AAIQ TAPE PWA) in staat om over het publieke internet real-time te communiceren met fysieke AAIQ Relay Box apparaten via uitgaande WebSocket-verbindingen, zonder dat poortforwarding of lokale routerconfiguratie op de studiolocatie vereist is.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Client PWA / Browser                            │
│                 https://taperc.aaiq.nl / /client/connect               │
└───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / WSS (TLS 1.3)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Reverse Proxy (Caddy / Nginx)                     │
│               Termineert TLS voor https://taperc.aaiq.nl               │
└───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP / WS (127.0.0.1:8080)
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      TAPERC Public Gateway Service                     │
│       Host: VPS Linux | User: aaiq | /opt/aaiq/taperc/public-taperc/   │
│   - Connection Manager & Session Registry                             │
│   - Cryptographic HMAC-SHA256 Challenge-Response Device Auth          │
│   - Separated Secrets Store (No plaintext keys in registry)          │
│   - Phase-1 Default Device compatibility routes (/api/v1/relay/...)   │
│   - Heartbeat & Auto-reconnect / Safe-state handling                   │
│   - Command-Response correlation & Live Telemetry Broadcasting        │
└───────────────────────────────────▲────────────────────────────────────┘
                                     │ WSS (Outbound connection)
                                     │ Endpoint: wss://taperc.aaiq.nl/device/connect
┌───────────────────────────────────┴────────────────────────────────────┐
│                  AAIQ Relay Box Pico W / Studio Node                   │
│                 (Geen poortdoorsturing op LAN vereist)                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Specificaties & Endpoints

| Eigenschap | Waarde |
|---|---|
| **Publieke URL** | `https://taperc.aaiq.nl` |
| **Device WebSocket** | `wss://taperc.aaiq.nl/device/connect` (pad: `/device/connect`) |
| **Client WebSocket** | `wss://taperc.aaiq.nl/client/connect` (pad: `/client/connect`) |
| **Health Endpoint** | `GET https://taperc.aaiq.nl/health` |
| **Info Endpoint** | `GET https://taperc.aaiq.nl/api/v1/info` |
| **Phase-1 Default Status** | `GET https://taperc.aaiq.nl/api/v1/status` |
| **Phase-1 Default Relay** | `POST https://taperc.aaiq.nl/api/v1/relay/{relay_id}` |
| **Phase-1 Default ON** | `POST https://taperc.aaiq.nl/api/v1/relay/{relay_id}/on` |
| **Phase-1 Default OFF** | `POST https://taperc.aaiq.nl/api/v1/relay/{relay_id}/off` |
| **Phase-1 Default Pulse** | `POST https://taperc.aaiq.nl/api/v1/relay/{relay_id}/pulse` |
| **Phase-1 Default All Off** | `POST https://taperc.aaiq.nl/api/v1/all/off` |
| **Explicit Device Status** | `GET https://taperc.aaiq.nl/api/v1/device/{device_id}/status` |
| **Explicit Device Info** | `GET https://taperc.aaiq.nl/api/v1/device/{device_id}/info` |
| **Explicit Relay Control** | `POST https://taperc.aaiq.nl/api/v1/device/{device_id}/relay/{relay_id}` |
| **Explicit Pulse Control** | `POST https://taperc.aaiq.nl/api/v1/device/{device_id}/relay/{relay_id}/pulse` |
| **Explicit All Off** | `POST https://taperc.aaiq.nl/api/v1/device/{device_id}/all/off` |
| **Linux User (VPS)** | `aaiq` |
| **VPS Deploymentpad** | `/opt/aaiq/taperc/public-taperc/` |

---

## 2. Bestandsstructuur

```text
gateway/public-taperc/
├── caddy/
│   └── Caddyfile.example           # Caddy 2 reverse proxy configuratie voor taperc.aaiq.nl
├── config/
│   ├── config.example.json         # Device registry metadata (geen plaintext secrets)
│   └── secrets.example.json        # Gescheiden secrets store (HMAC keys per secret_id)
├── deploy/
│   └── deploy.sh                   # Geautomatiseerd VPS deployment-, update- en recovery-script
├── src/
│   ├── __init__.py                 # Pakketinitialisatie (v1.0.0)
│   ├── app.py                      # AIOHTTP Application factory & lifecycle handlers
│   ├── auth.py                     # HMAC-SHA256 challenge-response & SecretsStore
│   ├── config.py                   # Dataclasses & configuratie-parser met .env overrides
│   ├── connection_manager.py       # Sessiebeheer, heartbeat-monitor & broadcasting
│   ├── protocol.py                 # Protocolberichten, schema-validatie & helpers
│   ├── routes.py                   # REST en WebSocket routing handlers
│   └── server.py                   # CLI startpunt en argumentenparser
├── systemd/
│   └── taperc-gateway.service      # Systemd service unit voor VPS deployment (/opt/aaiq/taperc/public-taperc)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures en test-applicatie setup
│   ├── test_auth.py                # HMAC challenge-response, replay & secrets tests
│   ├── test_config.py              # Configuratietests & env overrides
│   ├── test_connection_manager.py  # Sessie-, concurrent-, reconnect- & cleanup tests
│   ├── test_integration.py         # End-to-end WebSocket handshakes & event flows
│   ├── test_protocol.py            # Protocol validatie en hashing helpers
│   └── test_routes.py              # REST API & Phase-1 default device routes tests
├── .env.example                    # Voorbeeld omgevingsvariabelen
├── README.md                       # Deze documentatie en VPS deployment handleiding
└── requirements.txt                # Python runtime dependencies (aiohttp, pytest, etc.)
```

---

## 3. Beveiliging & HMAC Challenge-Response Handshake

### Scheiding van Registry en Secrets
- De device registry (`config.json` of `.env`) bevat uitsluitend apparaat-metadata en `secret_id` verwijzingen.
- Echte cryptografische HMAC secrets worden opgeslagen in een strikt afgeschermde secrets store (`secrets.json` of `TAPERC_SECRETS_FILE` / environment variabelen).
- Er staan geen plaintext secrets in de device registry.

### HMAC-SHA256 Handshake Protocol
1. **Verbinding Openen**: De Pico verbindt uitgaand met `wss://taperc.aaiq.nl/device/connect`.
2. **Gateway Challenge**: De gateway genereert een cryptografisch willekeurige nonce van 32 bytes (64 hex-tekens) en stuurt direct een challenge naar de verbinding:
   ```json
   {
     "type": "auth_challenge",
     "nonce": "c93b67484dfc80d467be56a0c0ad75df42b9195b0660683057e937d7a5bca949",
     "expires_in": 60,
     "timestamp": 1789218200.0
   }
   ```
3. **Pico Response**: De Pico berekent `HMAC-SHA256(secret_key, nonce)` en antwoordt:
   ```json
   {
     "type": "auth",
     "device_id": "AAIQ-RBP-001",
     "nonce": "c93b67484dfc80d467be56a0c0ad75df42b9195b0660683057e937d7a5bca949",
     "signature": "3f79e8c47b592160d5b4d4554b2d3080e81c1955dfc0bb146313b2d184a51e60",
     "firmware": "0.1.0",
     "relay_count": 8
   }
   ```
4. **Verificatie & Replay Protectie**:
   - De gateway controleert de challenge en verwijdert de nonce **onmiddellijk** uit de actieve nonces (single-use guarantee). Replay van een eerdere nonce faalt direct.
   - De vergelijking vindt plaats in constante tijd (`hmac.compare_digest`).
   - Bij succes stuurt de gateway `auth_ack(success=true)` en wordt de Pico als actief geregistreerd.

---

## 4. Fase-1 Default Device Routes

Voor naadloze compatibiliteit met bestaande PWA-clients en software kan de gateway commando's op de standaard paden automatisch routeren naar de `TAPERC_DEFAULT_DEVICE_ID`:

- `GET /api/v1/status` $\rightarrow$ status van standaard apparaat
- `POST /api/v1/relay/{n}` $\rightarrow$ relais aansturing standaard apparaat (`{"state": true/false}`)
- `POST /api/v1/relay/{n}/on` $\rightarrow$ relais inschakelen (`state=true`)
- `POST /api/v1/relay/{n}/off` $\rightarrow$ relais uitschakelen (`state=false`)
- `POST /api/v1/relay/{n}/pulse` $\rightarrow$ puls sturen (`{"duration_ms": 250}`)
- `POST /api/v1/all/off` $\rightarrow$ alle relais uitschakelen

Daarnaast blijven alle expliciete endpoints (`/api/v1/device/{device_id}/...`) volledig beschikbaar.

---

## 5. Tests Uitvoeren

Alle tests zijn geautomatiseerd met `pytest` en `pytest-aiohttp` / `pytest-asyncio`.

Voer de volledige testsuite uit:
```bash
python -m pytest gateway/public-taperc/tests/ -v
```

---

## 6. VPS Deployment & Beheer Handleiding

De TAPERC Public Gateway kan volledig geautomatiseerd worden geïnstalleerd, geüpdatet en hersteld via het meegeleverde script `deploy/deploy.sh`.

### Optie A: Geautomatiseerd via `deploy/deploy.sh` (Aanbevolen)

Het script `gateway/public-taperc/deploy/deploy.sh` automatiseert het beheer en waarborgt dat bestaande productieconfiguraties en secrets **nooit** worden overschreven.

```bash
# Naar de deployment directory navigeren
cd /opt/aaiq/taperc/public-taperc/deploy

# 1. Eerste installatie (idempotent):
sudo ./deploy.sh install

# 2. Veilige update (maakt automatische backup, updatet code, behoudt configs, runt tests & auto-rollback bij falen):
sudo ./deploy.sh update

# 3. Systeem- en health status controleren (lokaal & publiek):
sudo ./deploy.sh health

# 4. Handmatige backup maken:
sudo ./deploy.sh backup

# 5. Rollback uitvoeren (naar meest recente of specifieke backup):
sudo ./deploy.sh rollback
# of: sudo ./deploy.sh rollback /opt/aaiq/taperc/backups/taperc-backup-YYYYMMDD_HHMMSS.tar.gz
```

---

### Optie B: Handmatige Stap-voor-Stap Deployment Referentie

Volg onderstaande stappen indien u handmatig de gateway wilt installeren op de Linux VPS (`/opt/aaiq/taperc/public-taperc/`).

### Stap 1: Systeemgebruiker en Directory Structuur Aanmaken
Maak de afgeschermde servicegebruiker `aaiq` en het deploymentpad aan:
```bash
# Systeemgebruiker aaiq aanmaken (zonder login-shell)
sudo useradd -r -s /bin/false -d /opt/aaiq/taperc aaiq || true

# Doeldirectory's aanmaken
sudo mkdir -p /opt/aaiq/taperc/public-taperc/config
sudo mkdir -p /opt/aaiq/taperc/public-taperc/src
sudo mkdir -p /opt/aaiq/taperc/backups
sudo mkdir -p /var/log/caddy
```

### Stap 2: Bestanden Overbrengen naar `/opt/aaiq/taperc/public-taperc/`
Kopieer de gateway-bestanden naar `/opt/aaiq/taperc/public-taperc/`:
- `src/` (volledige directory)
- `config/config.example.json`
- `config/secrets.example.json`
- `deploy/deploy.sh`
- `.env.example`
- `requirements.txt`
- `systemd/taperc-gateway.service`
- `caddy/Caddyfile.example`

### Stap 3: Python Virtual Environment Inrichten
```bash
cd /opt/aaiq/taperc/public-taperc

# Python 3 venv initialiseren
sudo python3 -m venv /opt/aaiq/taperc/public-taperc/.venv

# Dependencies installeren
sudo /opt/aaiq/taperc/public-taperc/.venv/bin/pip install --upgrade pip
sudo /opt/aaiq/taperc/public-taperc/.venv/bin/pip install -r requirements.txt
```

### Stap 4: Productieconfiguratie & Geheime Sleutels Inrichten
Kopieer de voorbeeldbestanden en vul de echte cryptografische productiesleutels in:
```bash
cd /opt/aaiq/taperc/public-taperc

# Configuratiebestanden aanmaken
sudo cp config/config.example.json config/config.json
sudo cp config/secrets.example.json config/secrets.json
sudo cp .env.example .env

# Genereer sterke cryptografische keys (bv. openssl rand -hex 32)
# Bewerk config/secrets.json met de unieke HMAC keys per Pico Relay Box:
sudo nano config/secrets.json

# Bewerk .env met veilige waarden en master key:
sudo nano .env

# Beveilig bestandsrechten (alleen leesbaar voor aaiq)
sudo chown -R aaiq:aaiq /opt/aaiq/taperc
sudo chmod 750 /opt/aaiq/taperc /opt/aaiq/taperc/public-taperc
sudo chmod 600 /opt/aaiq/taperc/public-taperc/.env /opt/aaiq/taperc/public-taperc/config/secrets.json
```

### Stap 5: Systemd Service Activeren
Installeer de systemd unit om de gateway als background daemon te draaien:
```bash
# Service unit kopiëren
sudo cp /opt/aaiq/taperc/public-taperc/systemd/taperc-gateway.service /etc/systemd/system/

# Systemd herladen en service starten
sudo systemctl daemon-reload
sudo systemctl enable taperc-gateway
sudo systemctl restart taperc-gateway

# Status controleren
sudo systemctl status taperc-gateway
```

### Stap 6: Caddy 2 Reverse Proxy Configureren
Voeg de hostconfiguratie voor `taperc.aaiq.nl` toe aan `/etc/caddy/Caddyfile`:
```caddy
taperc.aaiq.nl {
    tls admin@aaiq.nl {
        protocols tls1.2 tls1.3
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    reverse_proxy 127.0.0.1:8080 {
        flush_interval -1
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}

        health_uri /health
        health_interval 10s
        health_timeout 2s
        health_status 200
    }

    log {
        output file /var/log/caddy/taperc.aaiq.nl.log {
            roll_size 10MiB
            roll_keep 10
            roll_keep_for 30d
        }
        format json
    }
}
```

Herlaad Caddy om de configuratie en automatische TLS-certificaten te activeren:
```bash
sudo systemctl reload caddy
```

### Stap 7: Verificatie & Smoke Testing
Valideer de werking direct op de VPS:
```bash
# Interne health check
curl -f http://127.0.0.1:8080/health

# Publieke health check via HTTPS
curl -f https://taperc.aaiq.nl/health

# Journalctl logs inzien
sudo journalctl -u taperc-gateway -f
```

---

## 7. Overzicht van Bestanden voor `/opt/aaiq/taperc/public-taperc/`

Bij deployment moeten de volgende bestanden uit `gateway/public-taperc/` worden overgezet:

```text
/opt/aaiq/taperc/public-taperc/
├── .env.example                    -> .env (met productie keys)
├── requirements.txt
├── config/
│   ├── config.example.json         -> config.json
│   └── secrets.example.json        -> secrets.json (chmod 600)
├── deploy/
│   └── deploy.sh                   -> geautomatiseerd beheer/updates/recovery
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── auth.py
│   ├── config.py
│   ├── connection_manager.py
│   ├── protocol.py
│   ├── routes.py
│   └── server.py
├── systemd/
│   └── taperc-gateway.service      -> naar /etc/systemd/system/
└── caddy/
    └── Caddyfile.example           -> toevoegen aan /etc/caddy/Caddyfile
```
