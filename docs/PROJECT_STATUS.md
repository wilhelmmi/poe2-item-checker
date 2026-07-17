# Projektstatus und nächster Schritt

Stand: 16. Juli 2026

## Produktziel

Der **PoE 2 Gear & Trade Checker** ist eine lokal selbst gehostete Web-App für englische
Path-of-Exile-2-Itemtexte. Build-Nutzen, Verkaufspotenzial und Crafting-Eignung werden
transparent und getrennt bewertet, ohne exakte DPS-Werte oder garantierte Marktpreise zu
behaupten. Oberfläche und Erklärungen bleiben deutsch; PoE-Bezeichnungen bleiben englisch.

## Umgesetzter Stand

### Basis, Parser und lokaler Faktencheck

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic und SQLite.
- React, TypeScript Strict Mode und Vite; Multi-Stage-Dockerfile und Compose-Konfiguration.
- Deterministischer, verlustbewahrender Parser für englische Itemtexte.
- Sichtbare Warnungen, sichere Zeilenumbruchvorschläge für kollabierte Texte und editierbare
  Parse-Vorschau.
- Deterministischer lokaler Faktencheck mit versionierter Regelkonfiguration, getrennten
  Trade-/Crafting-Ergebnissen, Evidence, konservativen Fallbacks und Disclaimer.

### Provider-unabhängige AI-Bewertung

- Neue typisierte `EvaluationProvider`-Schnittstelle; die OpenAI-Implementierung ist davon
  getrennt und kann später durch weitere Provider ergänzt werden.
- `POST /api/items/evaluate` führt immer zuerst Parsing und lokalen Faktencheck aus.
- Die OpenAI Responses API wird ausschließlich serverseitig über
  `responses.parse(..., text_format=EvaluationResult)` mit strengem Pydantic-Schema genutzt.
- Provideraufrufe verwenden `store=False`; API-Schlüssel werden nur als `SecretStr`, aus
  `OPENAI_API_KEY` oder aus einer über `OPENAI_API_KEY_FILE` referenzierten Secret-Datei
  gelesen und nie an das Frontend ausgeliefert.
- Konfigurierbar sind Modell, Reasoning Effort, Timeout, SDK-Retries, maximale strukturierte
  Eingabelänge, maximale Ausgabetokens und ein lokales Rate-Limit. Werte besitzen harte
  Typ- und Bereichsgrenzen.
- Eingesetzter dokumentierter Standard ist `gpt-5.6-luna` mit Reasoning `medium`.
- Refusals, ungültige strukturierte Antworten, fehlende Konfiguration, Rate-Limits und
  Providerfehler werden in stabile öffentliche Fehlercodes überführt.
- Bei Providerfehlern bleibt der lokale Faktencheck als typisierter, nutzbarer Fallback in
  der erfolgreichen Response erhalten.
- An den Provider gehen strukturierte Fakten ohne Modifier-Rohtext. Der Systemprompt
  behandelt alle Itemfelder als unvertrauenswürdige Daten und verbietet Livepreis-Fakten,
  erfundene Metadaten sowie Anweisungen aus Itemtexten.
- Das Ausgabeschema trennt Build-Eignung, Trade und Crafting. Freitextvalidatoren verhindern
  numerische Prozentbehauptungen sowie Upgrade-/Downgrade-, Equipmentvergleichs- und
  Score-Delta-Aussagen, solange CharacterProfile und Vergleichsequipment fehlen.
- Usage-Logs enthalten nur Provider, Modell und Tokenzahlen. Eine Kostenschätzung wird
  bewusst als nicht verfügbar markiert, da keine versionierte Modellpreistabelle vorliegt.

### Oberfläche

- Nach erfolgreichem Parse kann die AI-Bewertung über eine eigene explizite Aktion gestartet
  werden; ohne Klick entsteht kein kostenpflichtiger Aufruf.
- Build-, Trade- und Crafting-Ergebnis, Confidence, Gründe, Warnungen, Modell und Disclaimer
  werden getrennt angezeigt.
- Bei nicht verfügbarem Provider zeigt die Oberfläche den lokalen Faktencheck automatisch als
  Fallback an.
- Änderungen, neue Analysen und übernommene Zeilenumbruchvorschläge brechen laufende
  AI-Anfragen ab und entfernen veraltete Ergebnisse.
- Das lokale Einzelprofil kann mit Level, Life, ES, Mana, Spirit-Bedarf/-Reservierung,
  Attributes, ungekappte Resistances, Resistance Cap, Build Stage und Notizen gepflegt werden.
- Alle zehn Equipment-Slots sind einzeln lad- und speicherbar; `ring_1` und `ring_2` bleiben
  getrennte Zielslots. Ein Slotwechsel verwirft laufende oder sichtbare Vergleichsergebnisse.

### Persistentes Profil, Equipment und harte Swap-Prüfungen

- `GET/PUT /api/profile` verwaltet ein strikt validiertes, persistentes lokales Einzelprofil.
- `GET /api/equipment` liefert stets alle zehn Slots; `PUT /api/equipment/{slot}` parst den
  Itemtext serverseitig, prüft die Item Class und ersetzt den Slot transaktional. Ersetzte
  Items bleiben für spätere Historie erhalten.
- Der dokumentierte v1-Seed kann atomar importiert werden. Der verlustfreie v2-Export enthält
  alle Profilwerte und exakt alle zehn Slots einschließlich explizit leerer Slots; partielle
  v2-Snapshots werden abgelehnt.
- Zwei additive Alembic-Migrationen ergänzen Level und Spirit-Semantik sowie explizit leere
  Equipment-Slots, ohne die bestehende Initialmigration umzuschreiben.
- Der Parser normalisiert nun auch Strength, Dexterity, Intelligence und all Attributes.
- `POST /api/items/evaluate` akzeptiert optional `target_slot` und Profilnutzung. Kandidat und
  Slot werden vor dem Vergleich abgeglichen; beide Ring-Slots akzeptieren Rings.
- Deterministische, servereigene Hard Checks berechnen bekannte Requirements, Resistance-
  Caps, Spirit und Movement-Speed-Verlust aus Profil, Kandidat und Zielslot-Item. Fehlender
  Vergleichskontext ergibt `unknown`; Providerantworten können diese Fakten nicht verändern.

### Persistierte Candidates, History und Vollbackup

- `POST /api/items/evaluate` bleibt nebenwirkungsfrei; eine separate Save-Aktion parst und
  bewertet den Candidate serverseitig erneut gegen den aktuellen lokalen Stand.
- Evaluationen speichern lokale Scores, Category, Delta-Band, Confidence, Completeness,
  Regelversion und vollständige lokale Facts-/Hard-Check-/Comparison-Snapshots.
- Die stabil validierten Statuswerte sind `checked`, `equipped`, `stored`, `listed`, `sold`
  und `vendor`; Decimal-sichere Listing-/Sale-Daten und Notizen liegen in `SaleRecord`.
- History-Liste, Detail, Filter, Metadatenpflege und Recompare sind in API und deutscher UI
  verfügbar. Recompare ist append-only und referenziert den Vorgänger als Lineage.
- Das versionierte Vollbackup enthält Profil, Equipment einschließlich explizit leerer Slots,
  Items/Modifier, Evaluationen und Sales. Restore validiert Schema und Referenzen vollständig
  und ersetzt die lokale Domäne atomar.
- Migration `0004_evaluation_history` ist additiv und besitzt geprüfte Upgrade-/Downgrade-Pfade.

### Versionierte Build-Fit-Bewertung

- `app/rules/build-fit-v1.json` enthält die erste strikt validierte, versionierte lokale
  Gewichtung für den Chaos-DoT-Lich. Unbekannte Slots, Modifierkeys, fehlende Defence-Caps und
  unzulässige Gewichte oder Multiplikatoren lassen die Konfiguration früh fehlschlagen.
- Kandidat und ausgerüstetes Item werden mit demselben deterministischen Scorer von 0 bis 100
  bewertet. Jede Punktänderung besitzt eine Rule-ID und Evidence; auch das Begrenzen auf 0/100
  wird als eigener Schritt ausgewiesen, sodass die Evidence-Summe exakt dem Score entspricht.
- Beobachtetes Gesamt-Energy-Shield und zugrunde liegende ES-Affixe werden nicht doppelt
  gewertet. `reduced Cast Speed` wird als negative, begrenzte Build-Synergie erkannt.
- Unbekannte Modifier verändern den Score nicht. Sie markieren das Ergebnis als partiell und
  begrenzen positive Aussagen konservativ auf ein bedingtes Upgrade.
- Die Spezifikationsgrenzen sind maschinenlesbar: ab +12 Upgrade, +5 bis +11 bedingtes Upgrade,
  -4 bis +4 Sidegrade und ab -5 Downgrade; das genaue Delta-Band bleibt separat sichtbar.
- Nach einem Swap werden die Requirements des Kandidaten und aller verbleibenden Equipment-
  Items geprüft. Requirement-Verstöße ergeben `not_suitable`; neue Elemental-Undercaps,
  Spirit-Verstöße und starke Movement-Speed-Verluste begrenzen positive Kategorien.
- Eindeutige Itemklassen lösen ihren Zielslot automatisch auf. Rings ohne explizites Ziel
  werden gegen `ring_1` und `ring_2` verglichen; nur ein eindeutig besseres Delta wird empfohlen.
- Lokale Scores, Evidence, Kategorien und Hard Checks bleiben auch ohne API-Token vollständig
  verfügbar. Die AI-Ausgabe ist nachgeordnet und kann die lokale Entscheidung nicht ersetzen.

### Kalibrierte Build-Fit-v2-Regeln und Dateiworkflow

- `app/rules/build-fit-v2.json` ist die aktive, strikt validierte Regelversion. Die v1-Datei
  bleibt für reproduzierbare Vergleichstests erhalten.
- Geeignete additive Modifier werden linear nach ihrem einzelnen beobachteten Rollwert bis zu
  einem modifikatorspezifischen Cap gewichtet. Fehlende oder mehrdeutige Werte werden nicht
  geschätzt, sondern senken Vollständigkeit und Confidence.
- Gesamt-Energy-Shield und zugrunde liegende ES-Modifier werden weiterhin nie gemeinsam
  bewertet. Rollwert-Caps und beobachtete Werte stehen in der Evidence.
- Die vorhandenen Seed-Fixtures dokumentieren `v2 - v1`: Wand -24, Gloves -2, Boots -22.
- Die Vergleichsresponse liefert Regelversion, Confidence, Vollständigkeit, relevante und
  unbekannte Modifier sowie vorgruppierte Candidate-/Equipped-Gewinner und -Verlierer.
  Hard Checks bleiben separat und die lokale Kategorie bleibt die maßgebliche Entscheidung.
- Die UI importiert JSON-Dateien mit Schema v1/v2 nach lokaler Größen-, JSON- und
  Versionsprüfung. Backendfehler werden sicher und ohne Rohdatenanzeige ausgegeben.
  Der vollständige v2-Snapshot kann über die vorhandene Export-API heruntergeladen werden.

## Getroffene Entscheidungen

- Ohne CharacterProfile und ausgerüstetes Vergleichsitem wird nur **Build-Eignung** bewertet;
  Upgrade/Downgrade, Build-Fit-Score und Score-Delta wären derzeit nicht belastbar.
- Der lokale Faktencheck bleibt verpflichtender Guardrail und Fallback; AI-Ausgaben ersetzen
  ihn nicht.
- Es gibt keine Live-Marktdaten. Trade-Ausgaben bleiben heuristische Prüfempfehlungen und
  dürfen keine garantierten Preise behaupten.
- Die OpenAI-SDK-Retries sind begrenzt. Zusätzlich gilt ein einfacher In-Process-Sliding-
  Window-Limiter, passend zum aktuellen einzelnen Uvicorn-Prozess.
- Kein fester Euro-/Dollarpreis pro Token wird im Code gepflegt. Tokenzahlen werden geloggt,
  Kosten erst nach Einführung einer versionierten Preiskonfiguration geschätzt.
- Die bisher abweichend benannte Statusdatei `docs/implementation-status.md` wurde in diese
  kanonische `docs/PROJECT_STATUS.md` überführt, um doppelte Statusquellen zu vermeiden.
- Profilwerte für Attributes, Resistances und Spirit bedeuten aktuelle Character-Sheet-
  Gesamtwerte einschließlich des ausgerüsteten Items. Der Swap zieht dessen bekannte Beiträge
  ab und addiert die Beiträge des Kandidaten.
- Ein nicht vorhandener Slotdatensatz bedeutet „Vergleichsequipment unbekannt“; ein explizit
  leerer Slot bedeutet dagegen belastbar null Beitrag. Diese Zustände sind in Migration und
  Vergleichslogik getrennt.
- v1 bleibt als kompatibler Seed-Import erhalten. v2 ist bewusst ein vollständiger Snapshot,
  damit ausgelassene Slots oder Profilfelder keinen veralteten Zustand konservieren.
- Upgrade-/Sidegrade-/Downgrade-Kategorien und Scores bleiben weiterhin gesperrt; die neue
  AI darf sie weiterhin nicht bestimmen; freigeschaltet sind ausschließlich die neuen lokalen,
  versionierten Kategorien und Scores.
- Die numerischen Einzelgewichte sind eine neue Produktentscheidung, weil die Spezifikation nur
  Prioritäten und Delta-Schwellen vorgibt. Sie sind deshalb versioniert und über Evidence
  überprüfbar, statt als vermeintliche kanonische PoE-Werte dargestellt zu werden.

## Ausgeführte Tests und Prüfungen

- Backend: **114 Tests bestanden** (`pytest`). Darin enthalten sind die fünf dokumentierten
  Testitems mit Fake-Provider und ohne Netzwerk-/Kostenaufrufe.
- Ruff: ohne Befund.
- Python-`compileall`: erfolgreich.
- Frontend: **34 Vitest-Tests bestanden**.
- TypeScript-/Vite-Produktionsbuild: erfolgreich.
- `git diff --check`: ohne Befund.
- Geprüft wurden unter anderem Structured Outputs, `store=False`, Refusal und Rate-Limit,
  lokaler Fallback, ungültige Providerantworten, Settings-Grenzen, Secret-/Log-Leakage,
  verbotene Vergleichs-/Prozentbehauptungen, Profil-/Equipment-Persistenz, Ringtrennung,
  atomarer v1-Import, verlustfreier vollständiger v2-Roundtrip, Slot-Mismatches, explizit leere
  Slots, Missing-als-`unknown`, Score-/Evidence-Invarianten, sämtliche Delta-Grenzwerte,
  ES-Doppelzählung, negative Cast-Speed-Synergie, semantisch ungültige Regelkonfigurationen,
  verbleibende Equipment-Requirements, Ring-Doppelvergleiche und veraltete asynchrone
  UI-Antworten bei Profil-/Equipmentänderungen sowie v2-Konfigurationsgrenzen,
  Rollwert-Caps und reproduzierbare v1-v2-Fixture-Differenzen.
- Alembic-Upgrades bis `head` sowie gezielte Upgrade-/Downgrade-Prüfungen der neuen Migrationen
  liefen auf einer frischen SQLite-Datenbank erfolgreich.
- Es wurden keine Live-Aufrufe an OpenAI ausgeführt.
- Docker wurde in diesem Schnitt nicht erneut gebaut; in der Entwicklungsumgebung ist Docker
  weiterhin nicht installiert.

## Offene Risiken und Grenzen

- Der neue OpenAI-Pfad ist vollständig gemockt getestet, aber noch nicht mit einem echten
  Projekt-Key gegen die Live-API validiert. Modellzugang, Latenz und reale Rate-Limits können
  projektabhängig abweichen.
- Der In-Process-Rate-Limiter ist nicht verteilt und wird bei Neustart zurückgesetzt. Für einen
  einzelnen lokalen Prozess ist das akzeptabel; mehrere Worker benötigen einen gemeinsamen
  Limiter.
- Die App besitzt noch keine Authentifizierung. Das lokale Rate-Limit begrenzt Kosten, ersetzt
  aber keine Zugriffskontrolle bei Veröffentlichung außerhalb eines vertrauenswürdigen Netzes.
- Unbekannte Modifier bleiben im lokalen Faktencheck sichtbar. Die AI wird zur niedrigeren
  Confidence angewiesen, eine zusätzliche harte serverseitige Confidence-Kappung ist noch
  nicht implementiert.
- Nur bekannte additive Modifier fließen in Swap-Werte ein. Unbekannte oder nicht additive
  Effekte werden nicht geschätzt; manuell veraltete Character-Sheet-Werte können Ergebnisse
  entsprechend verfälschen.
- Die Build-Fit-v2-Gewichte sind eine nachvollziehbare Heuristik und noch nicht anhand
  größerer eigener Verkaufs-/Upgrade-Daten kalibriert. Scores sind relative Entscheidungshilfe,
  keine exakte DPS- oder Marktwertberechnung.
- Nicht alle Modifier sind sinnvoll rollwertabhängig. Skill-Level-Modifikatoren bleiben deshalb
  diskrete Präsenzregeln; unbekannte oder mehrwertige additive Effekte werden nicht geschätzt.
- OCR fehlt weiterhin. Persistenz geprüfter Kandidaten, lokale History und Vollbackup/Restore
  sind jetzt im Nutzerfluss verfügbar.
- Docker-Secret-Mounts müssen deploymentspezifisch eingerichtet werden; README und
  `.env.example` dokumentieren Env- und Key-File-Varianten.

## Empfohlener nächster Schritt

Vor einem neuen Produktmeilenstein muss der aktuelle Stand einmal als integrierter Nutzerfluss
abgenommen und gesichert werden. Danach bietet sich die **Kalibrierung anhand eigener geprüfter
History-Daten** an. Dazu gehören ein Review-/Label-Workflow und Auswertungen, die
Regeländerungen vor einer neuen Version reproduzierbar gegen alte Snapshots prüfen.
Live-Marktdaten bleiben ein separater, ausdrücklich opt-in Meilenstein.

## Übergabe für die nächste Sitzung

Stand beim Sitzungsende am 16. Juli 2026:

- Build-Fit v2, Dateiimport/-export, persistierte Candidates, History, Recompare,
  Verkaufsmetadaten sowie Vollbackup/Restore sind implementiert und dokumentiert.
- Die Implementierung liegt **noch uncommittet** im Arbeitsverzeichnis. Vorhandene Änderungen
  dürfen in der nächsten Sitzung nicht verworfen oder überschrieben werden.
- Die neue additive Migration `0004_evaluation_history` ist vorhanden, wurde in automatischen
  Upgrade-/Downgrade-Tests geprüft, muss aber für die lokale Anwendungsdatenbank noch mit
  `.venv/bin/alembic upgrade head` angewendet werden.
- Letzter vollständiger Prüfstand: **114 Backendtests** und **34 Frontendtests** bestanden;
  Ruff, `compileall`, TypeScript-/Vite-Build und `git diff --check` waren erfolgreich.
- Ein unabhängiger Code-Review wurde durchgeführt. Die Findings zu Restore-Sicherheit,
  Body-Limit, Backup-Referenzen, Candidate-/Status-Konsistenz, Sale-Validierung,
  asynchronen UI-Rennen und Pagination wurden behoben.
- Es wurden keine echten OpenAI-Aufrufe ausgeführt. Docker wurde für diesen Stand nicht gebaut.
- Es existiert noch kein Commit oder Pull Request für diese beiden Meilensteine.

In der nächsten Sitzung in dieser Reihenfolge fortfahren:

1. `git status` prüfen und die vorhandenen uncommitteten Änderungen beibehalten.
2. `.venv/bin/alembic upgrade head` auf der lokalen Datenbank ausführen.
3. Manuellen Browser-Smoke-Test durchführen: Profil/Equipment laden, Candidate bewerten und
   speichern, History filtern, Status und Sale-Daten pflegen, Recompare ausführen sowie
   Vollbackup herunterladen und nach ausdrücklicher Bestätigung wiederherstellen.
4. Wenn Docker verfügbar ist, den Multi-Stage-Build und den Containerstart prüfen.
5. Optional den Providerpfad einmal mit einem begrenzten Testprojekt/API-Key testen. Dabei
   keine Secrets oder vollständigen Itemtexte loggen oder in Fixtures übernehmen.
6. Anschließend Gesamttests wiederholen, Diff prüfen und den Stand auf einem Feature-Branch
   committen beziehungsweise als Draft Pull Request sichern.
7. Erst danach den nächsten Produktmeilenstein beginnen: Review-/Label-Workflow und
   Kalibrierungsauswertungen auf Basis der gespeicherten History. OCR folgt als separater
   späterer Meilenstein.
