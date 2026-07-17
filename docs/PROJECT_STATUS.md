# Projektstatus

Stand: 2026-07-17 — API-only Pivot umgesetzt und validiert.

## Aktives Produkt

- Candidate-vs-Equipped-Empfehlung über `POST /api/items/evaluate`.
- Ergebnis: `better | not_better | uncertain`, Confidence, Gründe, Warnungen.
- Kein lokaler fachlicher Score, Vergleich oder Empfehlungs-Fallback.
- Kein Marktwert-/Trade-Check und noch kein Crafting-Check.
- Lokales Parsing, Zielslot-Validierung und Profil-/Equipment-Persistenz bleiben aktiv.
- Parser-zertifizierte Autoformatierung arbeitet ausschließlich insert-only. Normal/Magic
  sowie Rare-Items mit zweigliedrigem Namen und erkanntem Basistyp werden nach erfolgreichem
  Identity-Reparse als `safe` eingestuft; kollabierte Unique- oder unvollständige Rare-Texte
  bleiben `ambiguous`. Evaluate und Equipment-Save verwenden ausschließlich `safe` automatisch.
- Das Slot-Eingabefeld formatiert vollständige Paste-Eingaben sofort sichtbar. Mehrdeutige
  Texte werden nur soweit sicher möglich strukturiert und bleiben vor dem Speichern prüfbar.
- Bulk-Imports bleiben verlustfrei und werden nicht stillschweigend autoformatiert.
- Die UI führt vor Vergleichen ein Parse-Preflight aus, zeigt Autoformatierung samt exaktem
  Undo und stoppt mehrdeutige Eingaben vor dem Provider-Aufruf.
- Provider erhält Candidate, exakt ausgerüstetes Zielslot-Item, Zielslot, beobachtetes Profil
  und den vollständigen versionierten Build-Kontext.
- Ein leerer Zielslot wird vor dem Provideraufruf mit `equipped_item_required` abgewiesen.
- Item-Rohtext, unbekannte Rohzeilen, Modifier-Rohtext sowie Profilname und -notizen werden
  nicht an den Provider übertragen. Beobachtete Prozent-Modifier, sachliche Trade-offs und
  die Tatsache eines crafted Modifiers sind in Gründen erlaubt. Unbelegte relative
  Leistungsprozente, Markt-/Preis-/Sale-Aussagen und Crafting-Handlungen oder -Empfehlungen
  werden schema-seitig verworfen. ValidationError-Logs enthalten nur Phase, Fehleranzahl,
  Typ/Ort und interne Rulecodes, nie Freitext, Input oder Validation-Context.

## Build-Registry

Aktuell registriert: `deadrabb1t-chaos-dot-lich-starter-v1`, Version 1,
`default-variant`, ED/Contagion Chaos DoT Lich Starter von DEADRABB1T. Neue Builds werden
als weitere versionierte Registry-Einträge ergänzt; Request und UI führen bereits `build_id`.

## Kompatibilität

Bestehende History-/Sale-Tabellen, Migrationen und Backup-Metadaten bleiben erhalten, um
den Dirty-Checkpoint nicht destruktiv umzuschreiben. History-Recompare und Sale-/Marktwert-
UI und die alten lokalen Check-/History-/Backup-Endpunkte sind nicht mehr Teil des aktiven
Produkts. Eine spätere Datenbereinigung braucht eine separate, bewusst freigegebene Migration.

## Validierung

- Ruff: ohne Befund.
- Backend: 144 Tests bestanden.
- Frontend: 14 Vitest-Tests bestanden.
- TypeScript-Prüfung und Vite-Produktionsbuild: erfolgreich.
- Code-Review durchgeführt; alle hoch priorisierten Findings wurden behoben.

## Nächster Meilenstein

1. Candidate-vs-Equipped mit echten API-Antworten und realen Equipment-Snapshots stabilisieren.
2. Zusätzliche Builds als neue Registry-Versionen aufnehmen.
3. Danach separaten API-basierten Crafting-Check entwickeln (Lohnt sich Crafting?).

Ein Marktwert-Check ist explizit nicht geplant.
