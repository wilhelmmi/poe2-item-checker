# PoE 2 Item Checker – vollständiges Codex-Briefing

> **Historischer Entwurf:** Dieses Dokument beschreibt den ursprünglichen Produktumfang und
> ist nicht der aktive API-Vertrag. Maßgeblich sind [README.md](../README.md) und
> [PROJECT_STATUS.md](PROJECT_STATUS.md). Insbesondere History-, Sale-, Marktwert- und alte
> lokale Check-Flows gehören nicht mehr zum aktiven Produkt.

## 1. Gesamtbewertung des bisherigen Konzepts

Das Vorhaben lohnt sich als kleine, selbst gehostete Web-App. Der Nutzen ist klar:

1. Neue Items werden strukturiert bewertet.
2. Das Item wird mit dem aktuell ausgerüsteten Gegenstand verglichen.
3. Die App trennt strikt zwischen:
   - **Eigenwert für den aktuellen Build**
   - **potenziellem Marktwert für andere Spieler**
4. Bewertungen und tatsächliche Verkäufe werden gespeichert, damit der Nutzer den Markt lernt.
5. Das Tool funktioniert unabhängig von Overlays und lokal laufendem PoE 2.

### Was am bisherigen Checker gut ist

- Das Ranking ist leicht verständlich:
  - Vendor
  - 1 Ex testen
  - Preis prüfen
  - mehrere Exalted
  - Divine+
- Der Checker berücksichtigt Base, Item Level, Modifier, Tiers und Synergie.
- Das aktuelle Equipment dient als Vergleichsbasis.
- Der Build ist bekannt: **Chaos DoT Lich nach DeadRabbit**.
- Die englischen Ingame-Bezeichnungen bleiben erhalten, während Erklärungen auf Deutsch erfolgen.
- Der Nutzer möchte bewusst bereits Items ab **1 Exalted Orb** einstellen.

### Was am bisherigen Checker verbessert werden muss

Der bisherige Chat-Checker war stellenweise zu grob und muss in der App präziser werden:

1. **Keine erfundenen Prozentangaben**
   - Nicht „8 % stärker“ behaupten, solange keine echte DPS-/Defensivberechnung vorliegt.
   - Stattdessen immer von **Score-Differenz**, **wahrscheinlichem Upgrade** oder **bedingtem Upgrade** sprechen.

2. **Marktwert nicht mit Listing-Preis verwechseln**
   - Wenige alte Listings beweisen keinen tatsächlichen Verkaufspreis.
   - Die App soll keinen exakten Live-Preis vortäuschen.
   - Ergebnis ist zunächst eine **Verkaufs-/Prüfempfehlung**, keine garantierte Bewertung.

3. **Resistances und Requirements berücksichtigen**
   - Ein Gegenstand kann isoliert besser wirken, aber durch den Tausch:
     - Resistances unter das Cap drücken,
     - Intelligence/Strength/Dexterity-Anforderungen verletzen,
     - Spirit-Anforderungen gefährden.
   - Deshalb muss die App den Tausch als Ganzes bewerten.

4. **Item Level nicht überbewerten**
   - Item Level ist für Crafting-Bases relevant.
   - Bei einem bereits identifizierten Rare zählen die tatsächlichen Mods stärker.
   - Ein niedriges Item Level macht ein gutes Übergangsitem nicht automatisch wertlos.

5. **Slot-spezifische Bewertung**
   - Movement Speed ist auf Boots entscheidend.
   - Skill Levels sind auf Wands entscheidend.
   - Spirit und Energy Shield können auf Amulets/Foci sehr wichtig sein.
   - Ein allgemeines, slotunabhängiges Punktesystem reicht nicht.

6. **Confidence anzeigen**
   - „High“, wenn Parsing und Regeln eindeutig sind.
   - „Medium“, wenn Charakterwerte fehlen.
   - „Low“, wenn die Einschätzung von aktueller Meta oder Live-Markt abhängt.

### Produktentscheidung

Die App ist **kein automatischer Preischecker**, sondern zunächst ein:

> Build-spezifischer Upgrade- und Trade-Kandidaten-Checker mit nachvollziehbarer Regel-Engine.

Das ist realistisch, transparent und für den Nutzer bereits sehr nützlich.

---

# 2. Auftrag an Codex

Baue eine produktionsfähige, lokal selbst gehostete Web-App mit dem Namen:

## **PoE 2 Gear & Trade Checker**

Die App läuft als einzelner Docker-Container und wird über Port `8080` bereitgestellt.

## Sprache

- Oberfläche und Erklärungen: **Deutsch**
- PoE-2-Bezeichnungen: **Englisch**
- Beispiele:
  - `Essence Drain`
  - `+1 to Level of all Chaos Spell Skills`
  - `Movement Speed`
  - `Energy Shield`

---

# 3. Nutzerkontext

- Spiel: Path of Exile 2
- Build: Chaos DoT Lich nach DeadRabbit
- Phase: frühes Endgame / Maps
- Plattform: GeForce NOW auf Linux
- Problem:
  - Itemtext lässt sich innerhalb der GFN-Session kopieren.
  - Das Kopieren aus GFN in die lokale Linux-Zwischenablage funktioniert nicht zuverlässig.
- Konsequenz:
  - Textimport ist notwendig.
  - Screenshot-Import mit OCR ist ebenfalls wichtig.
- Handelspräferenz:
  - Bereits potenziell brauchbare Items ab **1 Exalted Orb** einstellen.
  - Items nach 1–2 Tagen ohne Verkauf wieder entfernen oder vendorn.
- Ziel:
  - Marktverständnis aufbauen, nicht nur blind Preise übernehmen.

---

# 4. Funktionsumfang des MVP

## 4.1 Dashboard

Anzeigen:

- Build-Profil
- Build-Phase
- aktuelles Life
- aktuelles Energy Shield
- aktuelles Mana
- aktuelles Spirit
- Strength, Dexterity, Intelligence
- Fire, Cold, Lightning und Chaos Resistance
- offene Upgrade-Prioritäten
- zuletzt geprüfte Items
- aktuelle Verkaufskandidaten
- verkaufte Items und erzielte Preise

## 4.2 Equipment-Verwaltung

Slots:

- Wand
- Focus
- Helmet
- Body Armour
- Gloves
- Boots
- Belt
- Ring 1
- Ring 2
- Amulet

Funktionen:

- Itemtext einfügen
- Item automatisch parsen
- Slot automatisch erkennen
- Item manuell korrigieren
- Gegenstand als aktuell ausgerüstet speichern
- Equipment als JSON exportieren/importieren

Bei Rings:

- neues Item automatisch mit beiden Rings vergleichen
- anzeigen, welcher Ring eher ersetzt werden sollte
- Nutzer kann den Zielslot manuell ändern

## 4.3 Item Check

Eingabemöglichkeiten:

1. Itemtext einfügen
2. Screenshot hochladen
3. OCR-Ergebnis vor der Bewertung manuell korrigieren

Ausgabe:

### Eigenwert

- `Upgrade`
- `Bedingtes Upgrade`
- `Sidegrade`
- `Downgrade`
- `Nicht für diesen Build geeignet`

Zusätzlich:

- Build Fit Score, 0–100
- Score-Differenz zum aktuellen Item
- Gewinner und Verlierer nach Kategorien
- Warnungen bei:
  - Resistance-Verlust
  - fehlenden Attributes
  - Spirit-Verlust
  - Movement-Speed-Verlust
  - starkem Energy-Shield-Verlust

### Marktwert

- `Vendor`
- `1 Ex testen`
- `Preis prüfen`
- `Mehrere Exalted`
- `Divine+ Kandidat`

Zusätzlich:

- Trade Potential Score, 0–100
- Confidence: Low / Medium / High
- Begründungen
- Hinweis:
  - „Dies ist keine garantierte Live-Marktpreisermittlung.“

## 4.4 Historie

Pro geprüftem Item speichern:

- Zeitpunkt
- Rohtext
- geparste Daten
- Screenshot-Pfad, falls vorhanden
- Build Fit Score
- Trade Potential Score
- Empfehlung
- Status:
  - geprüft
  - ausgerüstet
  - eingelagert
  - gelistet
  - verkauft
  - Vendor
- Listenpreis
- tatsächlicher Verkaufspreis
- Zeit bis Verkauf
- Notizen

Filter:

- Slot
- Recommendation
- Status
- Datum
- Base Type
- Rarity

## 4.5 Lernfunktion

Bei einem Verkauf kann der Nutzer eingeben:

- Listenpreis
- Verkaufspreis
- Dauer bis Verkauf

Die App soll daraus noch keine automatische KI ableiten, aber Statistiken zeigen:

- durchschnittliche Verkaufsdauer
- häufig verkaufte Bases
- häufig verkaufte Modifier
- Items, die sofort verkauft wurden
- Items, die nach 48 Stunden nicht verkauft wurden

Warnung:

> „Sehr schneller Verkauf kann auf einen zu niedrigen Preis hindeuten, ist aber kein Beweis.“

---

# 5. Nicht-Ziele des MVP

Nicht implementieren:

- keine behauptete exakte Live-DPS-Berechnung
- keine garantierte Marktpreisermittlung
- kein automatisches Auslesen des laufenden Spiels
- kein Overlay
- kein Zugriff auf GeForce NOW
- kein automatisierter Handel
- kein Scraping ohne explizite, rechtlich und technisch geeignete Quelle
- keine externe KI-API als Pflicht

Optional später:

- offizielle oder zulässige Marktdatenquelle
- Build-Import
- Passive-Tree-Import
- mehrere Charaktere
- mehrere Build-Profile

---

# 6. Technischer Stack

## Vorgabe

Ein einzelner Docker-Container.

## Empfohlener Stack

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy oder SQLModel
- Pydantic
- SQLite

### Frontend

- React
- TypeScript
- Vite
- einfache, responsive Oberfläche
- kein unnötig großes UI-Framework
- optional Tailwind CSS

### Deployment

Multi-Stage-Dockerfile:

1. Frontend bauen
2. Python-Backend-Image bauen
3. statische Frontend-Dateien über FastAPI ausliefern

Persistente Daten:

```text
/data/app.db
/data/uploads/
/data/backups/
```

Port:

```text
8080
```

Healthcheck:

```text
GET /api/health
```

## Docker-Start

Beispiel:

```bash
docker run -d \
  --name poe2-checker \
  -p 8080:8080 \
  -v poe2-checker-data:/data \
  --restart unless-stopped \
  poe2-checker:latest
```

Optionales Environment:

```text
APP_SECRET=
BASIC_AUTH_USER=
BASIC_AUTH_PASSWORD=
MAX_UPLOAD_MB=10
OCR_ENABLED=true
BACKUP_RETENTION_DAYS=30
```

---

# 7. Datenmodell

## 7.1 CharacterProfile

```json
{
  "id": 1,
  "name": "Chaos DoT Lich",
  "build_stage": "early_endgame",
  "life": null,
  "energy_shield": null,
  "mana": null,
  "spirit": null,
  "strength": null,
  "dexterity": null,
  "intelligence": null,
  "fire_resistance": null,
  "cold_resistance": null,
  "lightning_resistance": null,
  "chaos_resistance": null,
  "resistance_cap": 75,
  "notes": ""
}
```

## 7.2 Item

```json
{
  "id": "uuid",
  "raw_text": "",
  "item_class": "Wands",
  "rarity": "Rare",
  "name": "Bramble Needle",
  "base_type": "Withered Wand",
  "required_level": 26,
  "item_level": 37,
  "quality": 0,
  "sockets": ["S"],
  "armour": null,
  "evasion": null,
  "energy_shield": null,
  "spirit": null,
  "granted_skill": "Level 10 Chaos Bolt",
  "identified": true,
  "corrupted": false,
  "modifiers": [],
  "created_at": ""
}
```

## 7.3 Modifier

```json
{
  "source": "explicit",
  "affix_type": "suffix",
  "name": "of Anarchy",
  "tier": 5,
  "tags": ["Chaos", "Caster", "Gem"],
  "raw_text": "+1 to Level of all Chaos Spell Skills",
  "normalized_key": "all_chaos_spell_skill_levels",
  "values": [1],
  "roll_ranges": [],
  "crafted": false,
  "desecrated": false,
  "rune": false,
  "implicit": false,
  "unique": false
}
```

Mögliche `source`-Werte:

- implicit
- explicit
- crafted
- desecrated
- rune
- unique
- granted_skill

## 7.4 EquipmentSlot

```json
{
  "character_id": 1,
  "slot": "wand",
  "item_id": "uuid"
}
```

## 7.5 Evaluation

```json
{
  "id": "uuid",
  "item_id": "uuid",
  "character_id": 1,
  "target_slot": "wand",
  "build_fit_score": 76,
  "equipped_item_score": 71,
  "score_delta": 5,
  "upgrade_recommendation": "conditional_upgrade",
  "trade_potential_score": 42,
  "trade_recommendation": "test_1_ex",
  "confidence": "medium",
  "reasons": [],
  "warnings": [],
  "created_at": ""
}
```

## 7.6 SaleRecord

```json
{
  "item_id": "uuid",
  "listed_at": "",
  "listed_currency": "Exalted Orb",
  "listed_amount": 1,
  "sold_at": null,
  "sold_currency": null,
  "sold_amount": null,
  "status": "listed",
  "notes": ""
}
```

---

# 8. Parser-Anforderungen

Der Parser muss den von PoE 2 über `Ctrl+C` erzeugten englischen Itemtext lesen.

## 8.1 Zu erkennende Felder

- Item Class
- Rarity
- Item Name
- Base Type
- Requirements
- Item Level
- Quality
- Sockets
- Armour
- Evasion
- Energy Shield
- Spirit
- granted skill
- Implicit Modifier
- Prefix Modifier
- Suffix Modifier
- Crafted Modifier
- Desecrated Modifier
- Rune Modifier
- Unique Modifier
- Tier
- Tags
- aktueller Wert
- Roll Range

## 8.2 Beispiele

```text
{ Prefix Modifier "Apprentice's" (Tier: 8) — Damage, Caster }
30(25-34)% increased Spell Damage
```

Erwartet:

```json
{
  "affix_type": "prefix",
  "name": "Apprentice's",
  "tier": 8,
  "tags": ["Damage", "Caster"],
  "normalized_key": "increased_spell_damage",
  "values": [30],
  "roll_ranges": [[25, 34]]
}
```

Beispiel:

```text
25% increased Spell Damage (rune)
```

Erwartet:

```json
{
  "source": "rune",
  "normalized_key": "increased_spell_damage",
  "values": [25],
  "rune": true
}
```

Beispiel:

```text
Energy Shield: 206 (augmented)
```

Erwartet:

```json
{
  "energy_shield": 206,
  "energy_shield_augmented": true
}
```

## 8.3 Parser-Regeln

- Originaltext immer speichern.
- Unbekannte Zeilen nicht verwerfen.
- Unbekannte Modifier als `normalized_key = "unknown"` speichern.
- Parserfehler in der UI sichtbar machen.
- Nutzer darf Felder manuell korrigieren.
- Parser muss idempotent sein:
  - gleicher Rohtext ergibt gleiches Parse-Ergebnis.

## 8.4 Tests

Mindestens Unit-Tests für:

- Rare Wand mit Rune und sechs Affixen
- Unique Gloves
- Magic Boots
- Rare Ring mit Crafted Modifier
- Item mit Desecrated Modifier
- Item mit mehreren Defences
- Item mit Granted Skill
- Item ohne Requirements
- Item mit zwei Sockets

---

# 9. OCR-Anforderungen

Da der Nutzer GeForce NOW verwendet, ist OCR wichtig.

## MVP-Variante

- PNG/JPG/WebP hochladen
- OCR auf englischen Text
- erkannter Text wird in einem editierbaren Textfeld angezeigt
- Bewertung erst nach Bestätigung durch den Nutzer

Technik:

- serverseitig `pytesseract` plus Tesseract-Paket im Docker-Image
- nur englisches Sprachmodell nötig
- Bildvorverarbeitung:
  - Kontrast erhöhen
  - Graustufen
  - optional zuschneiden
- niemals OCR-Ergebnis stillschweigend als sicher behandeln

Confidence:

- OCR Confidence anzeigen
- bei niedriger Confidence Warnung:
  - „Bitte Itemtext vor der Bewertung prüfen.“

---

# 10. Build-spezifische Bewertungsregeln

## 10.1 Build-Profil

```text
Build: Chaos DoT Lich
Stage: Early Endgame
Main archetype: Spell / Chaos / Damage over Time / Energy Shield
```

## 10.2 Globale Prioritäten

Sehr hoch:

- `+ Level to all Chaos Spell Skills`
- `+ Level to all Spell Skills`
- `increased Spell Damage`
- `increased Chaos Damage`
- hoher Energy Shield
- ausreichend Resistances
- ausreichende Intelligence
- Spirit, sofern für aktive Skills benötigt

Hoch:

- Cast Speed
- Maximum Energy Shield
- % increased Energy Shield
- Elemental Resistances
- Chaos Resistance
- Movement Speed auf Boots

Mittel:

- Maximum Life während Early Endgame, solange nicht auf reines CI/ES umgestellt
- Mana
- Mana Regeneration
- Intelligence
- Charm Slots
- Charm Effect Duration

Niedrig oder situationsabhängig:

- Life Regeneration
- Stun Threshold
- Accuracy
- Evasion auf reinem ES-Fokus
- Physical Thorns
- Mana per Enemy Killed
- Life per Enemy Killed

Für Chaos DoT meist sehr niedrig:

- Gain Damage as Extra Fire/Cold/Lightning
- increased Fire/Cold/Lightning Damage
- Attack Damage
- Bleeding
- Accuracy

Wichtig:

- `Gain X% of Damage as Extra Elemental Damage` darf nicht so bewertet werden, als würde es den Chaos-DoT vollständig skalieren.
- Ein solcher Mod ist für diesen Build normalerweise deutlich schwächer als Spell Damage, Chaos Damage oder Skill Levels.

---

# 11. Slot-spezifische Regeln

## Wand

Gewichtung:

1. +Chaos Spell Skill Levels
2. +All Spell Skill Levels
3. Spell Damage
4. Chaos Damage
5. Cast Speed
6. Mana / Mana Regeneration
7. Granted Skill als Utility

Abwertung:

- reine Attack Mods
- Accuracy
- Bleeding
- reine Elemental-Damage-Skalierung ohne passende Build-Synergie

## Focus

Gewichtung:

1. hoher Energy Shield
2. Spell Damage
3. Intelligence
4. Spirit
5. Energy Shield Recharge
6. Mana / Mana Regeneration
7. Resistances, falls verfügbar

## Body Armour

Gewichtung:

1. hoher Gesamt-Energy-Shield-Wert
2. flat Energy Shield
3. % increased Energy Shield
4. Resistances
5. Intelligence
6. Life im Early Endgame

## Helmet

Gewichtung:

1. Energy Shield
2. Resistances
3. Intelligence
4. Life im Early Endgame
5. Spirit

## Gloves

Gewichtung:

1. Spell Damage
2. Cast Speed
3. Energy Shield
4. Resistances
5. Intelligence

Unique-Effekte müssen als eigene Regeln erfasst werden.

Beispiel:

`Doedre's Tenure`

- +100% Spell Damage stark positiv
- reduced Cast Speed negativ
- Gesamtbewertung aus beiden Effekten, nicht nur aus einem Stat

## Boots

Gewichtung:

1. Movement Speed
2. Resistances
3. Energy Shield
4. Intelligence
5. Life

Schwellen:

- 30% Movement Speed: sehr stark
- 25%: stark
- 20%: brauchbar
- 15%: frühes Übergangsgear
- unter 15%: schwach im Endgame

## Amulet

Gewichtung:

1. Skill Levels, falls vorhanden
2. Spirit
3. % increased maximum Energy Shield
4. Resistances
5. Intelligence / all Attributes
6. Mana Regeneration

## Rings

Gewichtung:

1. Resistances
2. Intelligence
3. Chaos Damage
4. Life/Defensive Werte
5. Mana Regeneration
6. passende Implicits

Bei neuen Rings immer beide aktuellen Rings vergleichen.

## Belt

Gewichtung:

1. Charm Slots
2. Resistances
3. Life
4. Mana
5. Charm Effect Duration
6. Attributes

Thorns und Stun Threshold gering gewichten.

---

# 12. Build Fit Score

Bereich:

```text
0–100
```

Der Score ist slotabhängig.

## Vorgehen

1. Relevante Mods erkennen.
2. Mod-Tier berücksichtigen.
3. aktuellen Roll innerhalb des Tiers berücksichtigen.
4. Synergiebonus vergeben.
5. tote Mods nicht positiv werten.
6. Requirements- und Resistance-Warnungen berücksichtigen.
7. Score auf 0–100 begrenzen.

## Synergiebonus

Beispiele:

Wand:

- +Chaos Skills + Spell Damage + Cast Speed
- +Spell Skills + Chaos Damage

Boots:

- 30% Movement Speed + zwei Resistances + Energy Shield

Body Armour:

- hoher ES + %ES + Resistances + Intelligence

## Anti-Synergie

Beispiele:

- Spell Damage + Accuracy + Bleeding
- Chaos Caster Base + reine Attack Mods
- hohe Offensive, aber Tausch zerstört notwendige Resistance oder Intelligence

## Upgrade-Klassifikation

Nicht anhand fiktiver DPS-Prozente.

Empfohlene Logik:

- Score Delta >= 12:
  - Upgrade
- Score Delta 5 bis 11:
  - wahrscheinliches Upgrade
- Score Delta -4 bis +4:
  - Sidegrade
- Score Delta -5 bis -11:
  - wahrscheinliches Downgrade
- Score Delta <= -12:
  - Downgrade

Überschreibende Regeln:

- Tausch verletzt Requirements:
  - höchstens `Bedingtes Upgrade`
- Tausch senkt eine Elemental Resistance unter Cap:
  - Warnung und höchstens `Bedingtes Upgrade`
- großer Spirit-Verlust:
  - Warnung
- Boots verlieren mindestens 10% Movement Speed:
  - starke Warnung

---

# 13. Markt-/Trade-Bewertung

## Grundsatz

Die Trade-Bewertung ist eine heuristische Einstufung.

Sie darf nicht behaupten:

> „Dieses Item ist exakt 10 Exalted wert.“

Sie darf sagen:

> „Mehrere passende Mods und gute Synergie: Preis prüfen.“

## Trade Potential Score

Bereich:

```text
0–100
```

Faktoren:

- begehrte Base
- Item Level
- Rarity
- Anzahl guter Mods
- Tier der guten Mods
- Roll innerhalb des Tiers
- Synergie der Mods
- offene Affix-Slots
- Sockets
- Quality
- bekannte Build-Archetypen
- Unique-Bekanntheit, sofern als Regel hinterlegt

## Nutzerpräferenz

Der Nutzer möchte ab 1 Exalted testen.

Daher:

### Vendor

- schlechte Base
- keine gefragten Mods
- keine Synergie
- offensichtlich kein Crafting-Kandidat

### 1 Ex testen

- gute Base oder mindestens ein klar gefragter Mod
- brauchbares Übergangsitem
- 30% Movement Speed Boots mit zusätzlichem brauchbaren Mod
- gutes Magic Crafting-Item mit einem starken Affix
- Unsicherheit zugunsten des Nutzers

### Preis prüfen

- mindestens zwei bis drei gute, zusammenpassende Mods
- Premium-Mod
- hochwertige Crafting-Base
- seltene Kombination

### Mehrere Exalted

- starke Base
- mehrere starke Mods
- gute Synergie
- gute Tiers

### Divine+ Kandidat

- mehrere Premium-Mods
- sehr starke Synergie
- Top-Base
- sehr gute Tiers/Rolls
- hohe Confidence nur mit Marktprüfung

## Confidence

### High

- eindeutiges Vendor-Item
- eindeutig starke Mod-Kombination
- klare Build-Regel vorhanden

### Medium

- Charakterwerte unvollständig
- Item ist gut, aber Marktbedarf unklar
- mehrere plausible Archetypen

### Low

- Preis hängt stark von aktueller Season/Meta ab
- Unique ohne hinterlegte Regel
- wenige Vergleichsdaten
- OCR unsicher

---

# 14. Manuelle Marketplace-Unterstützung

Da keine Live-Preisdaten vorausgesetzt werden, soll die App eine manuelle Vergleichsmaske anbieten.

Felder:

- Anzahl gefundener Listings
- niedrigster Preis
- grober Median
- Alter des ältesten Listings
- Alter des günstigsten Listings
- Suchfilter/Notiz

Regeln:

- wenige Treffer + alte Listings:
  - Warnung vor Scheinpreis
- sehr viele Treffer bei 1 Ex:
  - eher kein Premium-Item
- sehr schneller eigener Verkauf:
  - möglicherweise zu günstig gelistet

Kein automatischer Schluss ohne Warnhinweis.

---

# 15. UI-Seiten

## `/`

Dashboard

## `/check`

- Tabs:
  - Itemtext
  - Screenshot
- Parse Preview
- manuelle Korrektur
- Evaluation

## `/equipment`

- alle Slots als Karten
- Klick öffnet Itemdetails
- Item austauschen
- Vergleichsansicht

## `/history`

- Tabelle und Filter
- Verkauf erfassen
- Status ändern

## `/profile`

- Character Sheet
- Build Stage
- Resistances
- Attributes
- Life / ES / Mana / Spirit

## `/settings`

- Regeln exportieren/importieren
- Datenbank-Backup
- OCR aktivieren/deaktivieren
- Authentifizierung
- Theme

---

# 16. Ergebnisdarstellung eines Checks

Beispiel:

```text
Cheetah's Dunerunner Sandals of the Narwhal

Eigenwert:
Bedingtes Upgrade

Build Fit:
72 / 100
Aktuelle Boots:
68 / 100
Delta:
+4

Vorteile:
+ 30% Movement Speed statt 15%
+ mehr Cold Resistance

Nachteile:
- weniger Fire Resistance
- weniger Lightning Resistance
- etwas weniger Energy Shield

Warnung:
Der Tausch kann Fire und Lightning Resistance unter das Cap drücken.

Marktwert:
1 Ex testen

Trade Potential:
41 / 100
Confidence:
Medium

Begründung:
30% Movement Speed ist für Leveling und frühe Maps gefragt. Der zweite Mod ist brauchbar, aber das Item hat keine weitere starke Defensivkombination.
```

---

# 17. Seed-Equipment

Beim ersten Start kann das aktuelle Equipment aus der beiliegenden Datei importiert werden:

```text
poe2-current-equipment.seed.json
```

Diese Daten sind die erste Vergleichsbasis.

Wichtige aktuelle Upgrade-Ziele:

1. Focus
2. Body Armour
3. Boots mit 30% Movement Speed, ohne Resistance-Cap zu verlieren
4. Amethyst Ring
5. Belt
6. Wand erst bei deutlich besserer Kombination

Diese Reihenfolge ist nur ein initialer Hinweis und muss anhand der eingegebenen Character-Sheet-Werte aktualisiert werden.

---

# 18. Akzeptanztests

## Test 1: aktueller Wand vs. schwacher Magic Wand

Aktueller Wand:

- +1 Chaos Spell Skills
- 78% Spell Damage inklusive Rune
- Granted Chaos Bolt

Neuer Magic Withered Wand:

- nur Extra Cold Damage

Erwartung:

- Eigenwert: klares Downgrade
- Markt: Vendor
- High Confidence

## Test 2: 30% Movement-Speed-Boots

Neues Item:

- 30% Movement Speed
- 20% Cold Resistance
- 63 Energy Shield

Aktuelle Boots:

- 15% Movement Speed
- 73 Energy Shield
- 12% Cold Res
- 19% Lightning Res
- 32% Fire Res

Erwartung:

- Eigenwert: bedingtes Upgrade oder Sidegrade
- starke Mobility-Verbesserung
- Warnung wegen Verlust von Fire/Lightning Resistance
- Markt: 1 Ex testen

## Test 3: Rare Vile Robe

Neues Item:

- 206 Energy Shield
- 96 Life
- 29% Fire Resistance

Aktuelle Body Armour:

- 131 Energy Shield
- 25% Fire Resistance
- 10 Intelligence

Erwartung:

- wahrscheinliches Upgrade
- Warnung bei möglichem Intelligence-Verlust
- Markt: 1 Ex testen oder Preis prüfen, abhängig von Regelgewichtung

## Test 4: Magic Vile Robe mit Spirit

- gute Base
- T6 Spirit
- Stun Threshold
- Item Level 65

Erwartung:

- für eigenen Build möglicherweise interessant, wenn Spirit benötigt wird
- Markt: 1 Ex testen
- kein behaupteter Preis von 10+ Ex nur wegen alter Listings

## Test 5: Dueling Wand mit Lightning Damage

- 84% increased Lightning Damage
- Mana Regeneration
- keine Skill Levels
- kein Spell Damage

Erwartung:

- für Chaos DoT Lich: ungeeignet
- Markt: Vendor oder maximal Low-Confidence 1 Ex Test bei besonderer Base-Regel
- Standard: Vendor

---

# 19. Qualitätsanforderungen

- TypeScript strict mode
- Python type hints
- Pydantic-Validierung
- Datenbankmigrationen
- Unit-Tests
- Integrationstests
- Parser-Fixtures
- klare Fehlermeldungen
- keine stillen Parsing-Fehler
- keine erfundenen Marktpreise
- Backup und Restore
- responsive Desktop-Oberfläche
- grundlegende mobile Nutzbarkeit

---

# 20. Projektstruktur

```text
poe2-checker/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── parser/
│   │   ├── scoring/
│   │   ├── services/
│   │   ├── db/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── data/
│   └── seed/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

---

# 21. API-Vorschlag

```text
GET    /api/health
GET    /api/profile
PUT    /api/profile
GET    /api/equipment
PUT    /api/equipment/{slot}
POST   /api/items/parse
POST   /api/items/ocr
POST   /api/items/evaluate
GET    /api/items/{id}
GET    /api/history
POST   /api/history/{id}/status
POST   /api/sales
PUT    /api/sales/{id}
GET    /api/export
POST   /api/import
POST   /api/backup
```

---

# 22. Implementierungsreihenfolge

## Phase 1

- Projektgerüst
- Docker
- SQLite
- Textparser
- Equipment
- Build Fit Score
- Vergleich
- Trade-Kategorien
- History
- Export/Import
- Tests

## Phase 2

- Screenshot-Upload
- OCR
- OCR-Korrektur
- verbesserte Statistik
- Backup-Rotation

## Phase 3

- mehrere Builds
- mehrere Charaktere
- erweiterbare Regelprofile
- optionale Marktdatenintegration
- Lootfilter-Verknüpfung

---

# 23. Definition of Done für Version 1.0

Version 1.0 ist fertig, wenn:

1. Die App als einzelner Docker-Container startet.
2. Daten nach einem Neustart erhalten bleiben.
3. Das aktuelle Equipment importiert werden kann.
4. Alle Testitems korrekt geparst werden.
5. Neue Items mit dem passenden Equipment-Slot verglichen werden.
6. Eigenwert und Marktwert getrennt angezeigt werden.
7. Resistances, Attributes, Spirit und Movement Speed als Warnungen berücksichtigt werden.
8. Die Kategorien Vendor / 1 Ex testen / Preis prüfen / mehrere Ex / Divine+ funktionieren.
9. Jede Empfehlung eine nachvollziehbare Begründung enthält.
10. Es keine behaupteten exakten Marktpreise ohne Datenquelle gibt.
11. Historie und Verkaufsstatus gespeichert werden.
12. Backup und Restore funktionieren.
13. README eine vollständige Portainer-/Docker-Anleitung enthält.

---

# 24. Codex-Arbeitsauftrag

Arbeite iterativ.

1. Erstelle zuerst Architektur, Datenmodelle und Parser.
2. Schreibe Tests für die beigefügten Seed- und Beispielitems.
3. Implementiere die regelbasierte Bewertung.
4. Implementiere erst danach die UI.
5. Zeige nach jedem größeren Schritt:
   - geänderte Dateien
   - Tests
   - offene Risiken
6. Keine stillen Annahmen zu PoE-Mechaniken treffen.
7. Regelgewichtungen in Konfigurationsdateien auslagern.
8. Keine Live-Marktpreise erfinden.
9. Dokumentiere jede Heuristik.
10. Liefere am Ende:
    - Dockerfile
    - docker-compose.yml
    - README
    - `.env.example`
    - Seed-Import
    - Testabdeckung
