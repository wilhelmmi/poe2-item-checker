# PoE 2 Build Item Checker

Die App beantwortet aktuell genau eine Frage: Ist ein eingefügter Item-Candidate für den
gewählten Build besser als das Item, das im gewählten Zielslot ausgerüstet ist?

Die fachliche Empfehlung kommt ausschließlich vom konfigurierten OpenAI-Provider. Lokal
bleiben Itemtext-Parsing, technische Slotvalidierung sowie Profil-/Equipment-Persistenz. Es
gibt keinen lokalen Score und keinen lokalen Empfehlungs-Fallback. Wenn der Provider oder
API-Key fehlt, zeigt die App deshalb **keine Empfehlung**.

## Builds

Standard ist `deadrabb1t-chaos-dot-lich-starter-v2`: **ED Contagion Chaos DoT Lich
Starter** von DEADRABB1T, Mobalytics-Variante `default-variant`. Der versionierte Kontext
enthält Essence Drain, Contagion, Dark Effigy und Despair sowie explizite offensive,
defensive und slotbezogene Item-Prioritäten. Die v1-Build-ID bleibt für bestehende Clients
und gespeicherte Vergleiche verfügbar. Weitere Builds können automatisch aus öffentlichen
Build-Links analysiert, als Vorschau geprüft und anschließend versioniert gespeichert werden.

Quelle: https://mobalytics.gg/poe-2/builds/chaos-dot-lich-starter-deadrabbit?ws-ngf5-f7d82102-7e77-4a44-ad24-33b67e8ae7bf=activeVariantId%2Cdefault-variant

## Start

```bash
cp .env.example .env
# OPENAI_API_KEY in .env setzen
docker compose up --build
```

Frontend: `http://localhost:8080`, API-Dokumentation: `http://localhost:8080/docs`.

Ohne Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## Aktiver API-Vertrag

### Eigene Builds aus Links

Im Build-Bereich kann eine öffentliche `http(s)`-URL analysiert werden. Der Server lädt die
URL nicht selbst, sondern übergibt sie der OpenAI Responses API mit Websuche und einem strikten
Ausgabeschema. Private IP-Adressen, localhost, Zugangsdaten und URL-Fragmente werden abgewiesen.
Ergebnisfelder und die tatsächlich vom Provider gelieferten URL-Zitate erscheinen zuerst als
Vorschau. Erst die Bestätigung speichert exakt diese Vorschau als versionierten Build.
Alle Builds – auch die beiden mitgelieferten – sind datenbankbasiert und löschbar. Wird der
letzte Build gelöscht, bleibt die Auswahl leer, bis wieder eine Vorschau bestätigt wird.

- `POST /api/builds/previews` analysiert `{ "source_url": "…" }`.
- `POST /api/builds/previews/{id}/confirm` bestätigt eine gültige Vorschau idempotent.
- `GET /api/builds` liefert eingebaute und eigene Builds weiterhin als Liste.
- `GET /api/builds/active` und `PUT /api/builds/active` verwalten die aktive Auswahl.
- `DELETE /api/builds/{build_id}` löscht den Build samt zugeordnetem Equipment.

Die Build-Analyse benötigt wie die Itembewertung einen konfigurierten `OPENAI_API_KEY`.
Die OpenAI-Websuche muss mindestens eine überprüfbare URL-Zitation liefern; ohne Zitation
wird keine Vorschau angeboten.

`POST /api/items/evaluate` verlangt `raw_text`, `target_slot` und akzeptiert `build_id`.
Der Provider erhält Candidate, das exakt im Zielslot ausgerüstete Item, den Zielslot,
beobachtete Profilwerte und den vollständigen versionierten Build-Kontext.
Ist der Zielslot leer, endet der Request vor dem Provideraufruf mit HTTP 422.
Das strukturierte Ergebnis enthält die kompatible `recommendation` (`better`,
`not_better`, `uncertain`) plus Urteil (`upgrade`, `sidegrade`, `downgrade`), Itemnamen,
begrenzte Gewinne und Verluste, vier Build-Auswirkungen und eine klare Empfehlung.
Der v2-Build mit expliziten Item-Prioritäten ist Standard; die v1-Build-ID bleibt verfügbar.

Die GUI erkennt aus der Itemklasse automatisch den Zielslot. Ringe verwenden den aktuell
gewählten Ring-Slot, ein Staff wird gemeinsam mit Wand und Fokus verglichen. Der API-Endpunkt
verlangt `target_slot` weiterhin explizit.

Der Python-Parser kennzeichnet Eingaben mit `auto_format_status` als `unchanged`, `safe`
oder `ambiguous`. Nur konservative, insert-only Vorschläge für einzeilige Normal-/Magic-
Items werden nach erfolgreichem Identitäts-Reparse automatisch angewendet. Einzeilige
Rare-/Unique-Items bleiben immer `ambiguous` und müssen manuell geprüft werden. Die UI zeigt
eine sichere Änderung als Hinweis; mehrdeutige Vorschläge werden nie automatisch an den
Provider gesendet oder als Equipment gespeichert.

`GET /api/builds` liefert die auswählbaren Build-Versionen. Equipment wird strikt je Build
unter `/api/builds/{build_id}/equipment` verwaltet; Import, Export und Ausrüsten verwenden
dieselbe Basis-URL. Alte Exporte bleiben beim Import kompatibel und werden dem ausgewählten
Build zugeordnet. Profilwerte und bestehende History-/Sale-Daten bleiben vorerst global. Die
Legacy-Backupfunktion arbeitet nur mit dem aktiven Build und verweigert Restore bei Equipment
weiterer Builds, damit kein fremdes Loadout überschrieben wird. Alte
History-/Sale-Daten und Datenbankfelder werden aus
Kompatibilitätsgründen nicht destruktiv migriert, gehören aber nicht mehr zum aktiven UI-
oder Bewertungsflow.

Die GUI kann vollständige Equipment-Snapshots mit `schema_version: 1` oder `2` sowie das
strukturierte Slotformat mit `wand`, `focus`, `helmet`, `body_armour`, `gloves`, `boots`,
`belt`, `ring1`, `ring2` und `amulet` atomar importieren. Importantwort und gespeicherter
Serverzustand werden anschließend gegeneinander verifiziert. Charms im strukturierten Format
werden erkannt, gehören aber noch nicht zu den unterstützten Equipment-Slots. Nach einem
erfolgreichen Vergleich ersetzt „Candidate ausrüsten“ das Item im exakt verglichenen Slot;
ein Staff belegt Wand und Fokus gemeinsam.

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
