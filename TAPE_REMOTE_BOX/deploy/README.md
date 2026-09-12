# AAIQ TAPE Remote Box — Deployment & Operations

Deze directory bevat de geautomatiseerde tooling en specificaties voor de uitrol, updates, backup, rollback en recovery van de **TAPERC Public Gateway** op de productie Linux VPS.

---

## 1. Doel & Bestanden

- **`deploy.sh`**: Idempotent bash-script voor volledige lifecycle-automatisering onder Linux runtime user `aaiq`.
- **`TAPERC_VPS_Deployment_and_Recovery.md`**: Uitgebreide documentatie over de VPS-inrichting, directory-rechten, fail-safe procedures en herstelstappen.
- **`caddy/Caddyfile.example`**: Reverse-proxy configuratie voor Caddy 2 met automatische TLS-terminatie voor `taperc.aaiq.nl`.
- **`systemd/taperc-gateway.service`**: Beveiligde systemd daemon unit met sandboxing (`ProtectSystem=full`, `NoNewPrivileges=true`).

---

## 2. CLI Commando's (`deploy.sh`)

Het script `deploy.sh` ondersteunt de volgende subcommando's:

```bash
# 1. Initiële installatie (idempotent):
sudo ./deploy.sh install

# 2. Veilige update (automatische pre-backup, dependency check, testvalidatie, auto-rollback bij falen):
sudo ./deploy.sh update

# 3. Lokale en publieke health checks:
sudo ./deploy.sh health

# 4. Handmatige backup maken:
sudo ./deploy.sh backup

# 5. Rollback naar meest recente of specifieke backup:
sudo ./deploy.sh rollback
# of: sudo ./deploy.sh rollback /opt/aaiq/taperc/backups/taperc-backup-YYYYMMDD_HHMMSS.tar.gz

# 6. Gateway testsuite uitvoeren:
sudo ./deploy.sh test
```

---

## 3. Productiepaden & Veiligheid

- **Doelpad**: `/opt/aaiq/taperc/public-taperc/`
- **Backups**: `/opt/aaiq/taperc/backups/`
- **Systeemeigenaar**: `aaiq:aaiq` (permissies `750` voor mappen, `600` voor `.env` en `secrets.json`)
- **Productieconfiguratie-bescherming**: `config.json` en `secrets.json` worden **nooit overschreven** tijdens updates.
