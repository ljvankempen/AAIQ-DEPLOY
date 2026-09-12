# TAPERC VPS Deployment & Recovery

**Project:** TAPERC — TAPE Remote Control  
**Document:** VPS Deployment, Update & Recovery  
**Status:** Current production deployment  
**Gateway version:** 1.0.0

## 1. Purpose

This is the central operational guide for the TAPERC Public Gateway on the AAIQ VPS. It is intended to make installation, updating, verification and recovery reproducible without reconstructing the procedure from chat history.

Future deployment work should preferably be automated and version-controlled.

## 2. Production architecture

```text
Phone / PC
    |
    | HTTPS
    v
https://taperc.aaiq.nl
    |
    v
Caddy
    |
    | reverse proxy
    v
127.0.0.1:8080
    |
    v
TAPERC Public Gateway
    |
    | outbound WSS
    v
TAPERC Pico 2 W
```

The Pico initiates the outbound WebSocket connection. No customer router port forwarding, VPN or router configuration is required.

Public endpoints:
- `https://taperc.aaiq.nl`
- `wss://taperc.aaiq.nl/device/connect`
- `wss://taperc.aaiq.nl/client/connect`

Internal gateway endpoint:
- `http://127.0.0.1:8080`

The gateway remains bound to localhost; Caddy provides public HTTPS.

## 3. VPS and users

Current VPS:
- Hostname: `aaiq-server`
- Public IPv4: `149.210.166.69`
- OS: Ubuntu 26.04.1 LTS
- Administrative SSH user: `ljvankempen`
- Runtime user: `aaiq`

User separation:

| User | Purpose |
|---|---|
| `ljvankempen` | VPS administration, sudo and deployment |
| `aaiq` | TAPERC Gateway runtime |

The gateway runs as `aaiq`. A separate SSH login for `aaiq` is not required.

## 4. Definitive filesystem

```text
/opt/aaiq/taperc/public-taperc/
```

Important paths:

```text
/opt/aaiq/taperc/
├── backups/                    # Timestamped deployment backups (chmod 700 / 600)
└── public-taperc/
    ├── .venv/
    ├── config/
    │   ├── config.json
    │   ├── config.example.json
    │   ├── secrets.json
    │   └── secrets.example.json
    ├── deploy/
    │   └── deploy.sh           # Automated deployment, update & recovery tool
    ├── src/
    ├── tests/
    ├── systemd/taperc-gateway.service
    ├── caddy/
    ├── requirements.txt
    └── README.md
```

The application directory must be owned/accessibly by `aaiq`.

## 5. Python environment

Runtime: Python 3.14.4

Virtual environment:

```text
/opt/aaiq/taperc/public-taperc/.venv
```

Install dependencies as the runtime user:

```bash
sudo -u aaiq /opt/aaiq/taperc/public-taperc/.venv/bin/python -m pip install -r /opt/aaiq/taperc/public-taperc/requirements.txt
```

## 6. Production configuration

Production configuration:

```text
/opt/aaiq/taperc/public-taperc/config/config.json
```

Important settings:

```text
server.host = 127.0.0.1
server.port = 8080
server.public_url = https://taperc.aaiq.nl
server.device_ws_path = /device/connect
server.client_ws_path = /client/connect
```

Security must remain enabled:

```text
require_client_auth = true
require_device_auth = true
```

The production secrets file is:

```text
/opt/aaiq/taperc/public-taperc/config/secrets.json
```

## 7. Secrets

Production secrets are separate from the device registry.

Required permissions:

```text
owner: aaiq:aaiq
mode: 600
```

Verify without displaying contents:

```bash
ls -l /opt/aaiq/taperc/public-taperc/config/secrets.json
```

Expected pattern:

```text
-rw------- 1 aaiq aaiq ...
```

Never:
- commit `secrets.json` to Git
- paste production secrets into chat
- put production secrets into example files
- overwrite production secrets during a normal application update
- display `secrets.json` contents during troubleshooting

## 8. Authentication

The implemented device authentication uses HMAC challenge-response:
- HMAC-SHA256
- random single-use challenge nonce
- constant-time comparison
- separate secrets store

The device registry references a `secret_id`; the actual secret is loaded from the separate secrets store.

Do not replace this with static bearer-token authentication.

## 9. Device/API behavior

Phase 1 default device:

```text
AAIQ-RBP-001
```

The gateway supports the existing API and both default-device and explicit-device routes.

The gateway must not automatically replay commands after reconnect.

Expected command outcomes include:

```text
command_result
DEVICE_TIMEOUT
DEVICE_OFFLINE
```

## 10. systemd

Installed unit:

```text
/etc/systemd/system/taperc-gateway.service
```

Project template:

```text
/opt/aaiq/taperc/public-taperc/systemd/taperc-gateway.service
```

The unit runs as `aaiq:aaiq` and uses:

```text
WorkingDirectory=/opt/aaiq/taperc/public-taperc
PYTHONPATH=/opt/aaiq/taperc/public-taperc
ExecStart=/opt/aaiq/taperc/public-taperc/.venv/bin/python -m src.server --config /opt/aaiq/taperc/public-taperc/config/config.json
```

After changing the unit:

```bash
sudo systemctl daemon-reload
```

Useful commands:

```bash
sudo systemctl start taperc-gateway
sudo systemctl restart taperc-gateway
sudo systemctl status taperc-gateway --no-pager
sudo systemctl enable taperc-gateway
sudo journalctl -u taperc-gateway -n 100 --no-pager
```

## 11. Health checks

Local API:

```bash
curl http://127.0.0.1:8080/api/v1/info
```

Public API:

```bash
curl -s https://taperc.aaiq.nl/api/v1/info
```

A response containing `"devices_online": 0` is normal when no Pico is connected.

Check listener:

```bash
sudo ss -ltnp | grep ':8080'
```

Expected listener:

```text
127.0.0.1:8080
```

## 12. Caddy

Configuration:

```text
/etc/caddy/Caddyfile
```

Current TAPERC route:

```caddy
taperc.aaiq.nl {
    reverse_proxy 127.0.0.1:8080
}
```

Validate before reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

Reload:

```bash
sudo systemctl reload caddy
```

Do not disturb routes belonging to other or future AAIQ applications.

## 13. Initial deployment reference

The successful deployment sequence was:

1. Create `/opt/aaiq/taperc`.
2. Ensure ownership is `aaiq:aaiq`.
3. Deploy `public-taperc`.
4. Ensure application ownership is `aaiq:aaiq`.
5. Create `.venv` as `aaiq`.
6. Install requirements as `aaiq`.
7. Run tests.
8. Create production `config.json`.
9. Generate production `secrets.json` directly on the VPS.
10. Set secrets permissions to `600`.
11. Install the systemd unit.
12. Run `systemctl daemon-reload`.
13. Start the gateway.
14. Verify the local API.
15. Configure Caddy reverse proxy.
16. Validate/reload Caddy.
17. Verify public HTTPS API.
18. Enable the systemd service for boot.

This is the reference deployment that future automation should reproduce.

## 14. Application update procedure

Normal application updates must preserve production state.

Never overwrite these during a normal source update:

```text
config/config.json
config/secrets.json
```

Preferred sequence:

```text
1. Backup current deployment
2. Deploy new application files
3. Preserve production config/secrets
4. Ensure ownership = aaiq:aaiq
5. Update/recreate .venv only when required
6. Install requirements as aaiq
7. Run tests
8. Validate configuration
9. Restart gateway
10. Check systemd status
11. Check local API
12. Check public API
```

The deployment should fail safely when tests or configuration validation fail.

## 15. Recovery procedure

A source-code backup alone is not a complete TAPERC recovery.

A complete recovery must account for:
- application source
- production `config.json`
- production `secrets.json`
- systemd unit
- Caddy routing
- DNS configuration
- definitive filesystem paths

Minimum recovery sequence:

```text
1. Confirm VPS access
2. Confirm /opt/aaiq/taperc exists
3. Confirm user aaiq exists
4. Restore application files
5. Restore production config.json
6. Restore production secrets.json securely
7. Set ownership and permissions
8. Create .venv as aaiq
9. Install requirements as aaiq
10. Run tests
11. Install systemd unit
12. daemon-reload
13. Start gateway
14. Verify local API
15. Validate Caddy
16. Verify public HTTPS API
17. Enable service at boot
```

Production secrets must have a secure backup outside Git.

## 16. Troubleshooting

Gateway status:

```bash
sudo systemctl status taperc-gateway --no-pager
```

Gateway logs:

```bash
sudo journalctl -u taperc-gateway -n 100 --no-pager
```

Service command:

```bash
sudo systemctl show taperc-gateway -p ExecStart
```

Application permissions:

```bash
ls -ld /opt/aaiq/taperc/public-taperc
ls -ld /opt/aaiq/taperc/public-taperc/.venv
ls -l /opt/aaiq/taperc/public-taperc/config/config.json
ls -l /opt/aaiq/taperc/public-taperc/config/secrets.json
```

Caddy:

```bash
sudo systemctl status caddy --no-pager
sudo caddy validate --config /etc/caddy/Caddyfile
```

If the local API works but the public API does not, investigate Caddy/DNS/HTTPS before changing gateway code.

## 17. Backups

Before replacing a production deployment, preserve at minimum:

```text
application source
config/config.json
config/secrets.json
/etc/systemd/system/taperc-gateway.service
/etc/caddy/Caddyfile
```

Do not put production secrets in Git or ordinary source archives.

## 18. Deployment automation tool (`deploy.sh`)

To satisfy the deployment automation requirement, a dedicated, reproducible, and version-controlled deployment tool is implemented at:

```text
/opt/aaiq/taperc/public-taperc/deploy/deploy.sh
```

### 18.1 Capabilities & Safety Principles

1. **Strict Production Preservation**: Production `config/config.json` and `config/secrets.json` are **never overwritten** during installation or update.
2. **Automated Pre-Update Backup**: Creates a timestamped `.tar.gz` archive in `/opt/aaiq/taperc/backups/` before any file modifications.
3. **Automated Rollback**: If tests, service restart, or local health checks fail during an update, the tool automatically rolls back to the previous working state.
4. **Isolated Runtime**: Runs exclusively with system user and group `aaiq:aaiq` (with `600` permissions on secrets).
5. **Safe Caddy Integration**: Validates `/etc/caddy/Caddyfile` without modifying or disrupting existing AAIQ Suite or third-party routes.
6. **Local & Public Health Verification**: Validates `http://127.0.0.1:8080/health`, `http://127.0.0.1:8080/api/v1/info`, and `https://taperc.aaiq.nl`.

### 18.2 Usage & Commands

```bash
cd /opt/aaiq/taperc/public-taperc/deploy

# Initial idempotent installation:
sudo ./deploy.sh install

# Safe application update (with pre-backup, testing & auto-rollback):
sudo ./deploy.sh update

# Standalone timestamped backup:
sudo ./deploy.sh backup

# Recovery / Rollback (restores latest backup or specified archive):
sudo ./deploy.sh rollback
# or specify archive:
# sudo ./deploy.sh rollback /opt/aaiq/taperc/backups/taperc-backup-YYYYMMDD_HHMMSS.tar.gz

# Comprehensive system & health status check:
sudo ./deploy.sh health

# Test suite execution inside virtualenv:
sudo ./deploy.sh test
```

## 19. Current verification record

Verified during this deployment:

```text
TAPERC tests: 34 passed
Relay Box tests: 33 passed
Gateway version: 1.0.0
Local API: working
Public HTTPS API: working
Caddy reverse proxy: working
systemd service: active
systemd boot enablement: configured
```

At the time of verification:

```text
devices_online = 0
```

This is expected because the Pico firmware had not yet been changed to establish the outbound WSS tunnel.

## 20. Next phase

The VPS gateway is ready for the Pico 2 W outbound WSS tunnel implementation.

Target:

```text
wss://taperc.aaiq.nl/device/connect
```

The Pico firmware must implement the agreed device authentication and command protocol.

The VPS gateway should not be changed unnecessarily while the Pico tunnel is developed.
