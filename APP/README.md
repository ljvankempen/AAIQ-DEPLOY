# AAIQ — APP Subproject

De **APP** directory binnen AAIQ-DEPLOY vormt de basis voor de toekomstige software- en cloudapplicaties van het AAIQ-ecosysteem.

---

## 1. Structuur

```text
APP/
├── profile/        # Gebruikersprofielen, studio-presets en apparaatconfiguraties
├── remote/         # Multi-device remote besturing en telemetrie UI
└── deploy/         # Geautomatiseerde deployment scripts en build pipelines
```

---

## 2. Architectuur & Relatie met AAIQ Studio

- **Centrale Orchestratie**: AAIQ Studio zal fungeren als de centrale orchestrator voor apparaatbeheer, audiostreaming en hardware-aansturing.
- **Strikte Scheiding**: Functionaliteit binnen `APP/` blijft onafhankelijk van firmware-relaismodules en communiceert via gestandaardiseerde API- en WebSocket-contracten.
- **Uitbreidbaarheid**: Geen verzonnen functies of mocks; modules worden stapsgewijs gevuld op basis van goedgekeurde AAIQ specificaties.
