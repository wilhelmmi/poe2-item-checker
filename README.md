# PoE 2 Build Item Checker

Die App beantwortet aktuell genau eine Frage: Ist ein eingefügter Item-Candidate für den
gewählten Build besser als das Item, das im gewählten Zielslot ausgerüstet ist?

Die fachliche Empfehlung kommt ausschließlich vom konfigurierten OpenAI-Provider. Lokal
bleiben Itemtext-Parsing, technische Slotvalidierung sowie Profil-/Equipment-Persistenz. Es
gibt keinen lokalen Score und keinen lokalen Empfehlungs-Fallback. Wenn der Provider oder
API-Key fehlt, zeigt die App deshalb **keine Empfehlung**.

## Unterstützter Build

Die Build-Registry enthält zunächst
`deadrabb1t-chaos-dot-lich-starter-v1`: **ED Contagion Chaos DoT Lich Starter** von
DEADRABB1T, Mobalytics-Variante `default-variant`. Der versionierte Kontext enthält Essence
Drain, Contagion, Dark Effigy und Despair sowie die Prioritäten Chaos-Spell-Level,
Spell-/Chaos-Damage, Cast Speed als Bonus, hohen Energy Shield, ES-Recharge, Resistenzen
und den Hinweis auf den hohen Mana-Bedarf. Die Registry und `build_id` im API-Vertrag sind
für weitere Builds vorbereitet.

Quelle: https://mobalytics.gg/poe-2/builds/chaos-dot-lich-starter-deadrabbit?ws-ngf5-f7d82102-7e77-4a44-ad24-33b67e8ae7bf=activeVariantId%2Cdefault-variant

## Start

```bash
cp .env.example .env
# OPENAI_API_KEY in .env setzen
docker compose up --build
```

Frontend: `http://localhost:8000`, API-Dokumentation: `http://localhost:8000/docs`.

Ohne Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Aktiver API-Vertrag

`POST /api/items/evaluate` verlangt `raw_text`, `target_slot` und akzeptiert `build_id`.
Der Provider erhält Candidate, das exakt im Zielslot ausgerüstete Item, den Zielslot,
beobachtete Profilwerte und den vollständigen versionierten Build-Kontext.
Ist der Zielslot leer, endet der Request vor dem Provideraufruf mit HTTP 422.
Das strukturierte Ergebnis enthält ausschließlich `recommendation` (`better`,
`not_better`, `uncertain`), `confidence`, `reasons` und `warnings`.

Der Python-Parser kennzeichnet Eingaben mit `auto_format_status` als `unchanged`, `safe`
oder `ambiguous`. Nur konservative, insert-only Vorschläge für einzeilige Normal-/Magic-
Items werden nach erfolgreichem Identitäts-Reparse automatisch angewendet. Einzeilige
Rare-/Unique-Items bleiben immer `ambiguous` und müssen manuell geprüft werden. Die UI zeigt
eine sichere Änderung mit Undo auf den exakten Originaltext; mehrdeutige Vorschläge werden
nie automatisch an den Provider gesendet oder als Equipment gespeichert.

`GET /api/builds` liefert die auswählbaren Build-Versionen. Profil- und Equipment-Endpunkte
bleiben bestehen. Alte History-/Sale-Daten und Datenbankfelder werden aus
Kompatibilitätsgründen nicht destruktiv migriert, gehören aber nicht mehr zum aktiven UI-
oder Bewertungsflow.

## Qualität

```bash
.venv/bin/ruff check app tests
.venv/bin/pytest -q
cd frontend && npm test -- --run && npm run build
```

## Roadmap

Nach einem stabilen Candidate-vs-Equipped-Vergleich folgt ein separater API-basierter
Crafting-Check, der beurteilt, ob sich das Craften eines Items lohnt. Ein Marktwert- oder
Trade-Check ist nicht vorgesehen.
