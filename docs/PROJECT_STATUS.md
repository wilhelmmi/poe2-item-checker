# Projektstatus

Stand: 2026-07-21 — Equipment-, Bewertungs- und Custom-Build-Flows umgesetzt und validiert.

## Aktives Produkt

- Candidate-vs-Equipped-Empfehlung über `POST /api/items/evaluate`.
- Ergebnis: kompatible Empfehlung (`better | not_better | uncertain`), konsistentes
  Upgrade-/Sidegrade-/Downgrade-Urteil, Gewinne, Verluste, vier Build-Auswirkungen,
  Confidence, Warnungen und klare Ausrüstungsempfehlung.
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
- Der v1/v2/v3-Equipmentimport und das strukturierte Slotformat ohne
  `schema_version` sind implementiert. Importantwort und gespeicherter Zustand werden durch
  ein anschließendes `GET /api/equipment` verifiziert. Der reale GUI-Smoke-Test ist erfolgt.
- Nach einer erfolgreichen API-Empfehlung kann der Candidate explizit ausgerüstet werden.
  Dabei wird exakt der verglichene Zielslot atomar ersetzt und die alte Vergleichsaussage
  unmittelbar invalidiert. Das vorherige Item bleibt nur intern nicht-destruktiv erhalten.
- Die UI führt vor Vergleichen ein Parse-Preflight aus, weist auf sichere Autoformatierung hin
  und stoppt mehrdeutige Eingaben vor dem Provider-Aufruf.
- Provider erhält Candidate, exakt ausgerüstetes Zielslot-Item, Zielslot, beobachtetes Profil
  und den vollständigen versionierten Build-Kontext.
- Der v2-Build priorisiert Chaos-/Spell-Skill-Level, Schaden, Cast Speed und die defensiven
  bzw. Utility-Werte in fester Reihenfolge; schwache Stats sind explizit niedriger gewichtet.
- Die strukturierte Antwort liefert Gewinne, Verluste, vier Build-Auswirkungen, ein konsistentes
  Upgrade-/Sidegrade-/Downgrade-Urteil und eine klare Ausrüstungsempfehlung. v1 bleibt abrufbar.
- Die GUI erkennt den Candidate-Slot aus der Itemklasse automatisch. Ringe werden mit beiden
  Ringpositionen und Charms mit maximal drei Charmpositionen verglichen; die AI benennt den
  empfohlenen Ersatzslot, ein leerer Alternativslot wird bevorzugt. Alternative Positionen
  werden nie gemeinsam ersetzt. Ein Staff wird gegen Wand und Fokus als gemeinsames Paket
  verglichen und ersetzt beim Ausrüsten beide Slots atomar.
- Charm-Slots werden durch die explizite Kapazität des ausgerüsteten Gürtels freigeschaltet
  (maximal drei, konservativer Fallback `charm_1`). Gesperrte leere Slots sind keine
  Vergleichs- oder Ausrüstungsziele; belegte Legacy-Slots bleiben sichtbar.
- Öffentliche Build-Links werden über die OpenAI-Websuche analysiert. Nur Analysen mit
  überprüfbaren URL-Zitationen werden als Vorschau angeboten; erst die Bestätigung speichert
  einen versionierten Build. Alle Builds sind DB-basiert und löschbar; null Builds sind zulässig.
- Ein leerer einzelner Zielslot wird mit `equipped_item_required` abgewiesen. Leere Ring- und
  durch den Gürtel freigeschaltete Charm-Alternativslots sind gültig und werden als
  verlustfreies erstmaliges Ausrüsten bewertet.
- Item-Rohtext, unbekannte Rohzeilen, Modifier-Rohtext sowie Profilname und -notizen werden
  nicht an den Provider übertragen. Beobachtete Prozent-Modifier, sachliche Trade-offs und
  die Tatsache eines crafted Modifiers sind in Gründen erlaubt. Unbelegte relative
  Leistungsprozente, Markt-/Preis-/Sale-Aussagen und Crafting-Handlungen oder -Empfehlungen
  werden schema-seitig verworfen. ValidationError-Logs enthalten nur Phase, Fehleranzahl,
  Typ/Ort und interne Rulecodes, nie Freitext, Input oder Validation-Context.

## Build-Registry

Bei Migration 0006 werden `deadrabb1t-chaos-dot-lich-starter-v1` für Kompatibilität und
`deadrabb1t-chaos-dot-lich-starter-v2` als Standard in der Datenbank angelegt, jeweils `default-variant`,
ED/Contagion Chaos DoT Lich Starter von DEADRABB1T. Bestätigte Link-Analysen werden als
weitere versionierte Builds gespeichert; Request und UI führen `build_id`. Equipment ist
über diese ID vollständig getrennt. Profilwerte und gespeicherte Evaluationen bleiben global;
die nicht mehr im UI angebotene Legacy-Backup-/Local-History-Logik liest nur Equipment des
aktiven Builds und verweigert einen mehrdeutigen Multi-Build-Restore sicher.

## Kompatibilität

Bestehende History-/Sale-Tabellen, Migrationen und Backup-Metadaten bleiben erhalten, um
den Dirty-Checkpoint nicht destruktiv umzuschreiben. History-Recompare und Sale-/Marktwert-
UI und die alten lokalen Check-/History-/Backup-Endpunkte sind nicht mehr Teil des aktiven
Produkts. Eine spätere Datenbereinigung braucht eine separate, bewusst freigegebene Migration.

## Validierung

- Ruff: ohne Befund.
- Backend: 181 Tests bestanden.
- Frontend: 44 Vitest-Tests bestanden.
- TypeScript-Prüfung und Vite-Produktionsbuild: erfolgreich.
- Code-Review durchgeführt; alle hoch priorisierten Findings wurden behoben.

## Equipmentimport: abgenommen

Der ursprüngliche GUI-Smoke-Test am 2026-07-17 zeigte trotz ausgewählter Importdatei keinen
serverseitig belegten Zielslot. Die Untersuchung am 2026-07-20 identifizierte eine
Port-/Instanzverwechslung: Docker veröffentlicht Port 8080, während die Dokumentation
fälschlich Port 8000 nannte.

Die Dokumentation ist korrigiert. Zusätzlich verifiziert die GUI einen Import durch ein
anschließendes
`GET /api/equipment`, validiert beide Serverantworten und zeigt Schema-, Slot- oder
Persistenzabweichungen verständlich an, statt einen nicht bestätigten Erfolg zu melden.
Der strukturierte Import speichert zusätzlich bis zu drei Charms. Da dieses Legacy-Format
für Charms nur Rarity, Name und Base enthält, bleiben deren Modifier bewusst leer; es werden
keine Stats erfunden. Vollständige v3-Snapshots exportieren alle 13 Slots.

## Nächster Meilenstein

1. Candidate-vs-Equipped mit weiteren echten API-Antworten und Equipment-Snapshots
   stabilisieren.
2. Weitere Buildquellen und unvollständige bzw. JavaScript-abhängige Seiten im
   Vorschau-Workflow erproben.
3. Danach separaten API-basierten Crafting-Check entwickeln (Lohnt sich Crafting?).

Ein Marktwert-Check ist explizit nicht geplant.
