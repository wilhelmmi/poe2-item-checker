# Implementierungsstand und nächster Projektschnitt

Stand: 15. Juli 2026

## Produktziel

Der **PoE 2 Gear & Trade Checker** ist eine lokal selbst gehostete Web-App für englische
Path-of-Exile-2-Itemtexte. Sie soll Build-Nutzen, Verkaufspotenzial und Crafting-Eignung
transparent und getrennt bewerten, ohne exakte DPS-Werte oder garantierte Marktpreise zu
behaupten.

Oberfläche und Erklärungen bleiben deutsch; PoE-Bezeichnungen bleiben englisch.

## Implementierter Stand

### Backend und Infrastruktur

- Python 3.12, FastAPI, Pydantic v2 und SQLAlchemy 2.
- SQLite mit aktivierten Foreign Keys.
- Explizite Alembic-Initialmigration.
- Modelle und Pydantic-Verträge für CharacterProfile, Item, Modifier, EquipmentSlot,
  Evaluation und SaleRecord.
- `GET /api/health`.
- Multi-Stage-Dockerfile und Compose-Konfiguration für Port 8080 und `/data/app.db`.
- React, TypeScript Strict Mode und Vite.

### Itemimport und Parsing

- Deterministischer englischer Itemtextparser ohne I/O, IDs oder Zeitabhängigkeit.
- Vollständiger Originaltext bleibt unverändert erhalten.
- Unbekannte Zeilen und unbekannte Modifier werden nicht verworfen.
- Requirements, Properties, Defences, Sockets, Granted Skills, Modifierheader, Tier, Tags,
  Werte und Roll Ranges werden verarbeitet.
- Mehrzeilige Affixe behalten ihre Header-Metadaten.
- `POST /api/items/parse` mit typisierten Warnungen und Zeilenreferenzen.
- Editierbare Parse-Vorschau im Frontend.

### Kollabierte Einzeilentexte

- Einzeilige GFN-/Clipboard-Texte werden nicht stillschweigend als vollständig interpretiert.
- Der Server erzeugt ausschließlich sichere, deterministische Zeilenumbruchvorschläge.
- Vorschläge sind insert-only: Kein Originalzeichen wird gelöscht, verschoben oder ersetzt.
- Der Nutzer prüft und bearbeitet den Vorschlag, übernimmt ihn ausdrücklich und startet erst
  danach eine erneute Analyse.

### Lokaler Faktencheck

- `POST /api/items/check` arbeitet deterministisch und ohne Datenbankzugriff.
- Vollständige beobachtbare Projektion der Parserdaten als Item- und Modifierfakten.
- Versionierte, streng validierte Regelkonfiguration unter `app/rules/facts-v1.json`.
- Kleine Predicate-Sprache ohne `eval`, mit Prioritäten und Modifiergruppen.
- Verkauf und Crafting sind getrennte Ergebnisse.
- Konservative Fallbacks: `manual_review` und `needs_review` statt erfundener Aussagen.
- Evidence, Rule-ID, Confidence-Gründe, Warnungen und permanenter Disclaimer.
- Unbekannte relevante Modifier verhindern eine scheinbar sichere Empfehlung.

## Aktuelle Validierung

- Backend: 59 Tests bestanden.
- Ruff: ohne Befund.
- Frontend: 8 Vitest-Tests bestanden.
- TypeScript-/Vite-Produktionsbuild: erfolgreich.
- Python-`compileall`: erfolgreich.
- `git diff --check`: ohne Befund.
- Docker konnte lokal nicht gebaut werden, weil Docker in der Entwicklungsumgebung nicht
  installiert ist. Das Backend und Frontend wurden lokal erfolgreich gestartet.

## Bewusste Grenzen

- Keine Persistenz geprüfter Items im aktuellen Nutzerfluss.
- Kein Equipmentvergleich und keine Upgrade-/Downgrade-Aussage.
- Keine OCR-, Authentifizierungs-, Backup- oder History-Funktion.
- Keine Live-Marktdaten und keine garantierte Preisermittlung.
- Lokale Regeln können die kombinatorische Vielfalt der PoE-Modifier nicht vollständig
  abdecken. Sie bleiben deshalb als transparente Guardrails und Fallback erhalten, sollen
  aber nicht zu einem vollständigen PoE-Regellexikon ausgebaut werden.
- Positive Crafting-Regeln fehlen bewusst, solange keine belastbaren Daten oder expliziten
  Akzeptanzkriterien vorliegen.

## Architekturentscheidung für AI-Bewertung

Als nächster Hauptweg ist die offizielle OpenAI API vorgesehen. Hermes Agent bleibt ein
optionaler späterer Provider. Beide müssen hinter derselben austauschbaren
`EvaluationProvider`-Schnittstelle liegen.

Die lokale Anwendung bleibt verantwortlich für:

- Parsing und Verlustfreiheit,
- beobachtbare Itemfakten,
- harte Validierung und Guardrails,
- Warnungen und Disclaimer,
- Prüfung der strukturierten Modellausgabe,
- später harte Equipment-, Resistance-, Requirement- und Spirit-Prüfungen.

Der AI-Provider darf übernehmen:

- Interpretation beliebiger Modifierkombinationen,
- Build-Synergien und Anti-Synergien,
- getrennte Trade- und Crafting-Einschätzung,
- verständliche Gründe und Confidence.

Die AI darf ohne externe Datenquelle keine aktuellen Marktpreise als Fakten ausgeben.

## Geplanter nächster Implementierungsschnitt

1. Provider-unabhängige `EvaluationProvider`-Schnittstelle definieren.
2. OpenAI Responses API ausschließlich serverseitig integrieren.
3. API-Zugang über `OPENAI_API_KEY` beziehungsweise Docker Secret einlesen; niemals an das
   Frontend ausliefern oder im Repository speichern.
4. Modell und Reasoning konfigurierbar machen, initial beispielsweise:

   ```text
   OPENAI_MODEL=gpt-5.6-luna
   OPENAI_REASONING_EFFORT=medium
   ```

5. Striktes Pydantic-Schema für getrennte Ergebnisse definieren:
   - Build-/Eigenwert ohne behauptete DPS-Prozente,
   - Verkaufsempfehlung,
   - Crafting-Einschätzung,
   - Confidence,
   - Gründe und Warnungen.
6. Timeout, begrenzte Retries, maximale Ein-/Ausgabelänge, Rate-Limit und verständliche
   Providerfehler implementieren.
7. Tokenverbrauch und grobe Kosten protokollieren, ohne Secrets oder unnötige Itemdaten zu
   loggen.
8. Die dokumentierten Testitems als Evaluation-Suite verwenden und Antworten mocken; Tests
   dürfen keine kostenpflichtigen Live-Aufrufe voraussetzen.
9. Lokalen Faktencheck als Guardrail und Fallback behalten.
10. Hermes später als zweiten Provider über seinen OpenAI-kompatiblen lokalen HTTP-Endpunkt
    ergänzen.

## Erwarteter Start im nächsten Chat

Vor Änderungen vollständig lesen:

1. `AGENTS.md`
2. `docs/poe2-item-checker-codex-spec.md`
3. diese Datei

Danach den OpenAI-Projektschnitt erneut gegen aktuelle offizielle OpenAI-Dokumentation prüfen,
die konkreten Sicherheits-/Kostenentscheidungen bestätigen und gemäß `AGENTS.md` mit
`project-explorer`, `feature-implementer` und `code-reviewer` umsetzen.

## Nicht verändern

- Keine echten API-Schlüssel in `.env`, Logs, Fixtures, Screenshots oder Commits aufnehmen.
- `AGENTS.md` und Agent-TOML-Dateien nur bei einem tatsächlichen Konfigurationsfehler ändern.
- Keine Commits oder Pushes aus zukünftigen Implementierungsschritten, sofern sie nicht
  ausdrücklich angefordert werden.
