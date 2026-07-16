# PoE 2 Gear & Trade Checker

Lokaler erster Projektschnitt mit FastAPI, SQLAlchemy/Alembic, strikt typisiertem
React/Vite-Frontend, verlustbewahrendem Parser und einem konservativen regelbasierten
Faktencheck. Equipmentvergleich, Upgrade- oder Score-Logik, OCR, Livepreise und eine
vollständige produktive UI sind bewusst noch nicht implementiert.

## Schnellstart auf einem neuen Rechner

Voraussetzungen: Git, Python 3.12, Node.js 22 und npm.

```bash
git clone https://github.com/wilhelmmi/poe2-item-checker.git
cd poe2-item-checker

python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
.venv/bin/alembic upgrade head

cd frontend
npm ci
cd ..
```

Danach Backend und Frontend in zwei Terminals starten:

```bash
# Terminal 1 (Repository-Root)
.venv/bin/uvicorn app.main:app --reload --port 8080

# Terminal 2 (Repository-Root)
cd frontend
npm run dev
```

Das Frontend ist anschließend unter `http://localhost:5173` erreichbar. Alternativ lässt
sich das gesamte Projekt mit `docker compose up --build` starten.

## Lokale Entwicklung

Voraussetzungen: Python 3.12, Node.js 22 und npm.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
DATABASE_URL=sqlite:///./app.db .venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Frontend separat starten:

```bash
cd frontend
npm ci
npm run dev
```

Der Vite-Dev-Server leitet `/api` standardmäßig an `http://127.0.0.1:8080` weiter.
Für abweichende Entwicklungsumgebungen kann das Ziel mit
`VITE_API_PROXY_TARGET=http://app:8080 npm run dev` überschrieben werden.

Die Frontend-Abhängigkeiten sind auf konkrete Versionen festgelegt und durch
`package-lock.json` reproduzierbar aufgelöst. Das Dockerfile verwendet ebenfalls `npm ci`.

## Tests und Builds

```bash
.venv/bin/pytest
.venv/bin/ruff check app tests
cd frontend && npm run test && npm run build
docker build -t poe2-checker:latest .
```

## Pull Requests und CI

Änderungen werden auf einem Feature-Branch umgesetzt und lokal mit den oben genannten
Prüfungen validiert. Nicht triviale Änderungen werden zusätzlich durch einen Review-Agenten
geprüft. Anschließend wird der Branch gepusht und ein Draft Pull Request gegen `main`
geöffnet; Commits oder automatische Merges direkt auf `main` sind nicht Teil dieses Ablaufs.

GitHub Actions führt für Pull Requests gegen `main` die Backend-Prüfungen mit Python 3.12,
die Frontend-Tests und den Frontend-Build mit Node.js 22 sowie danach einen vollständigen
Docker-Build ohne Push aus. Der Workflow kann außerdem manuell gestartet werden und prüft
den Stand von `main` nach einem Merge erneut.

Damit GitHub den Ablauf erzwingt, muss für `main` in den Repository-Einstellungen ein
Branch Ruleset oder eine Branch-Protection-Regel mit folgenden Vorgaben eingerichtet werden:

- Änderungen nur über Pull Requests zulassen; eine GitHub-Freigabe ist nicht erforderlich,
  da nicht triviale Änderungen bereits lokal durch einen Review-Agenten geprüft werden.
- Die Statuschecks `Backend`, `Frontend` und `Docker` vor dem Merge voraussetzen.
- Direkte Pushes auf `main` unterbinden; Ausnahmen und Force-Pushes nicht zulassen.
- Automatisches Mergen deaktiviert lassen.

Die Regeln werden bewusst in GitHub konfiguriert, da sie nicht allein durch eine Datei im
Repository wirksam erzwungen werden können.

## Container

```bash
docker compose up --build
```

Oder direkt:

```bash
docker run --rm -p 8080:8080 -v poe2-checker-data:/data poe2-checker:latest
```

Die API ist unter `GET /api/health` erreichbar. SQLite liegt im Container standardmäßig unter `/data/app.db`; Migrationen werden vor dem Serverstart ausgeführt.

## Itemtext manuell analysieren

`POST /api/items/parse` strukturiert englischen Itemtext ohne Speicherung oder Bewertung:

```bash
curl -X POST http://localhost:8080/api/items/parse \
  -H 'Content-Type: application/json' \
  -d '{"raw_text":"Item Class: Rings\nRarity: Normal\nIron Ring"}'
```

Der Originaltext wird unverändert zurückgegeben. Einzeilige Texte wie das reale Beispiel in
`docs/example-items.txt` können nicht zuverlässig rekonstruiert werden: In der Oberfläche
müssen die Trennmarker und Itemfelder manuell auf eigene Zeilen gesetzt und anschließend
erneut analysiert werden. Unvollständige Ergebnisse bleiben sichtbar und enthalten stabile
Warncodes statt vorgetäuschter Vollständigkeit.

Die Response enthält `item` als strukturierte Vorschau und `warnings`. Jede Warnung hat
einen stabilen `code`, deutschen `message`-Text sowie `lines` und `raw_lines`. Globale
Warnungen verwenden dort leere Listen. Aktuell existieren:

- `input_missing_line_breaks`
- `unknown_lines_preserved`
- `missing_item_identity`
- `no_modifiers_detected`

Die Vorschau zeigt ausschließlich Parserdaten. Sie speichert nichts und trifft keine
Aussage zu Ausrüstung, Build-Eignung, Wert oder Handel. Ein kollabierter Einzeiler wird
absichtlich nicht strukturiert interpretiert, sondern vollständig als unbekannte Zeile
zur manuellen Korrektur zurückgegeben.

Bei eindeutig erkennbaren Grenzen kann die Response zusätzlich eine nullable
`line_break_suggestion` mit `suggested_text` und sortierten `insertions` enthalten. Der
`offset` jeder Insertion ist nullbasiert und bezieht sich auf den unveränderten Originaltext.
Vorschlag fügt ausschließlich Zeilenumbrüche ein: exakte `--------`-Trennmarker,
Item-Class-/Rarity-Grenzen, kanonische Rarity-Werte und syntaktisch vollständige
Modifierheader. Namen, Bases, Wertebereiche und Freitext werden nicht heuristisch getrennt.
Die Oberfläche hält diesen editierbaren Entwurf vom Original getrennt. Übernehmen oder
Verwerfen startet keine Analyse; nach dem Übernehmen ist ein explizites „Erneut
analysieren“ erforderlich. Der Vorschlag ist keine Vollständigkeitszusage.

## Lokaler Faktencheck

Nach einem vollständigen Parse kann `POST /api/items/check` oder der explizite Button
„Faktencheck ausführen“ verwendet werden. Der Check ist deterministisch, nutzt nur die
versionierte lokale JSON-Regelkonfiguration und speichert nichts. Verkauf und Crafting
werden getrennt ausgewiesen; unbekannte Kombinationen fallen auf `manual_review` bzw.
`needs_review` zurück. Evidence enthält Regel-ID, Begründung und passende Fakten.

Der Faktencheck ist ausdrücklich kein Equipmentvergleich, keine Upgrade-Empfehlung und
keine Live-Preisermittlung. Der serverseitige Disclaimer ist Bestandteil jeder erfolgreichen
Einschätzung. Unvollständige oder kollabierte Parserdaten liefern keine Einschätzung und
den Warncode `assessment_skipped`.

Modifier-Coverage bedeutet hier ausschließlich: Der normalisierte Schlüssel ist in der
versionierten Registry bekannt. Unbekannte explizite, implizite oder einzigartige
Modifier erzwingen konservativ `manual_review` und `needs_review`; ein separat erfasstes
Granted Skill ohne eigene Normalisierung zählt nicht automatisch als unbekannter Affix.
Rollpositionen werden nur bei genau einem Wert und einer Range arithmetisch berechnet,
nicht begrenzt; umgedrehte oder außerhalb liegende Ergebnisse erzeugen Warncodes.
