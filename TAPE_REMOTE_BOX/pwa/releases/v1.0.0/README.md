# AAIQ TAPE Remote — Standalone Progressive Web App (PWA)

De **AAIQ TAPE Remote PWA** is de zelfstandige webapplicatie voor de besturing van vintage en professionele bandrecorders (zoals de Revox PR99 en Revox B77). De app draait als moderne Progressive Web App in mobiele en desktopbrowsers (iOS Safari, Android Chrome, macOS Safari, Windows/Linux Desktop) en communiceert over veilige HTTPS/WSS verbindingen met de **TAPERC Public Gateway** (`https://taperc.aaiq.nl`) of lokaal via de Pico 2 W Webserver.

---

## 1. Functies & UI Componenten

1. **Dual-Reel Deck Animatie**:
   - Real-time visuele weergave van de bandspoelen.
   - Snelheids- en draairichting-animaties synchroon met transportstatus (`spinning`, `spinning-fast`, `spinning-rev`, of stilstand).

2. **Transportbesturing Grid (6 Tactiele Knoppen)**:
   - `REW` (Relais 6 — GP16)
   - `PLAY` (Relais 1 — GP21)
   - `FF` (Relais 5 — GP17)
   - `RECORD` (Relais 3 — GP19)
   - `PAUSE` (Relais 4 — GP18)
   - `STOP` (Relais 2 — GP20)
   - Inclusief LED statusindicatie, pulsfeedback en haptische trilling (`navigator.vibrate(35)`).

3. **Power Interlock Beveiliging (Relais 8 — GP14)**:
   - Veilige in-/uitschakeling van de deck-voeding.
   - Mechanische interlock: Uitschakelen is beveiligd geblokkeerd zolang een transportfunctie actief is (eerst `STOP` vereist).

4. **PWA Installatie & Caching**:
   - Standalone modus zonder browser-URL-balk.
   - Service Worker (`sw.js`) met automatische cache-versiebeheer (`tape-remote-v1.0.0`).
   - Dynamische logo-caching (GitHub raw -> localStorage -> lokale fallback).
   - Platform-specifieke installatiemodals voor iOS Safari, Android Chrome, Mac Dock en Desktop browsers.

---

## 2. Bestandsstructuur

```text
pwa/
├── css/
│   └── style.css           # Studio Dark Slate thema & animaties
├── images/
│   ├── app-icon.png
│   ├── apple-touch-icon.png
│   ├── icon-192.png
│   ├── icon-512.png
│   ├── icon.svg            # Schaaldbaar vector deck-icoon
│   └── logo.png            # AAIQ merklogo
├── js/
│   └── app.js              # REST API communicatie, statuspolling, transport logica
├── index.html              # Hoofdpagina PWA
├── manifest.json           # Web App Manifest
├── sw.js                   # Service Worker voor offline caching & asset lifecycle
└── README.md               # Deze documentatie
```

---

## 3. Hosting & Deployment

De PWA-bestanden kunnen op drie manieren worden geserveerd:
1. **Centraal via de VPS Gateway (`https://taperc.aaiq.nl`)**: Caddy of AIOHTTP serveert de statische assets direct met HTTP/2 en TLS 1.3.
2. **Lokaal via LAN Gateway (`https://aaiq-rc.local`)**: Lokale Caddy-proxy op de studio-locatie.
3. **Embedded Fallback**: Direct vanuit de MicroPython firmware op poort 80 (`/remote`).

---

## 4. Caching & Versiebeheer Strategie

- Statische assets (`/css/*`, `/js/*`, `/images/*`, `/manifest.json`) worden door de Service Worker gecachet.
- API-aanroepen (`/api/*`) worden **nooit gecachet** (`fetch` pass-through).
- Bij een nieuwe release wordt `CACHE_NAME` in `sw.js` opgehoogd, waarna oude caches direct worden opgeruimd bij de `activate`-gebeurtenis (`self.clients.claim()`).
