# Animem (Python / Flask)

Komplette Neuumsetzung von Animem 2.0 (Next.js + PostgreSQL) in **Python**. Gleiche Funktionen, gleiches Design (Gelb / Neon-Grün / Rot), aber:

- **Nur ein Paket nötig:** `Flask` (alles andere ist Python-Standardbibliothek)
- **SQLite statt PostgreSQL** – keine Datenbank-Server, läuft direkt in Termux
- **Kein Node, kein Build-Schritt** – HTML-Templates + ein CSS + ein JS-File

## Start in Termux

```bash
pkg install python
cd animem-py
pip install -r requirements.txt     # oder nur: pip install flask
cp .env.example .env                # OWNER_EMAIL eintragen
python app.py                       # → http://localhost:5000
```

Datenbank und Ordner werden beim ersten Start automatisch angelegt (`data/`).

## Owner einrichten

1. In `.env` die eigene E-Mail bei `OWNER_EMAIL` (optional `OWNER_USERNAME`) eintragen.
2. Normal auf `/register` registrieren.
3. `python manage.py make-owner deine@mail.de`

Danach: `/owner` (Datenbank-Explorer, Audit-Log, System) und `/admin`.

## Verwaltungsbefehle

| Befehl | Zweck |
|---|---|
| `python manage.py list-users` | Alle Konten anzeigen |
| `python manage.py set-role MAIL ADMIN` | Rolle setzen (USER / ADMIN / HEAD_ADMIN) |
| `python manage.py reset-password MAIL` | Passwort neu setzen (beendet alle Sitzungen) |
| `python manage.py disable-2fa MAIL` | 2FA eines ausgesperrten Kontos abschalten |

## Tests

```bash
python -m unittest discover -s tests -v
```

## Deployment (Render)

`render.yaml` liegt bei. Wichtig: SQLite und Uploads brauchen eine **Persistent Disk** (nicht im Free-Plan), sonst gehen Daten bei jedem Neustart verloren. Die Datei setzt dafür `ANIMEM_DB_PATH=/var/data/animem.db` und `ANIMEM_STORAGE_DIR=/var/data/uploads`. `TRUST_PROXY=1` ist dort Pflicht, damit Rate-Limits die echte Client-IP sehen.

## Bewertung, Tracking und Ranking (so funktioniert es)

- **Bewertung pro Staffel (1–10)**, wie bei MyAnimeList – jede Staffel hat ihre eigene Wertung und ihre eigenen Kommentare. Die Wertung der ganzen Serie ist der Durchschnitt aller Staffel-Stimmen. Filme werden direkt bewertet.
- **Automatisches Tracking:** Es gibt keinen manuellen Status. Wer eine Folge öffnet, hat die Serie unter „Schaue ich gerade“; nach **3 Minuten** auf der Folgenseite gilt die Folge als gesehen (der Server prüft die Zeit nach, per API lässt sich das nicht abkürzen). Sind alle veröffentlichten Folgen gesehen, wandert die Serie unter „Abgeschlossen“. Manuell gibt es nur Watchlist und Abo.
- **Staffel-Bilder:** Jede Staffel kann im Admin-Editor ein eigenes Bild bekommen (leer = Serien-Poster). Angezeigt wird immer die *aktuelle* Staffel des Nutzers: noch nie geschaut → Staffel 1, Staffel 1 fertig → Staffel 2 usw. Ein Klick auf die Serie öffnet direkt diese Staffel. Sind alle Staffeln gesehen, bleibt die letzte.
- **Ranking** (`/ranking`, Startseiten-Podest = Top 3 „aller Zeiten“): Jede **Staffel tritt einzeln an** – ist Staffel 2 besser bewertet als Staffel 1, steht sie weiter oben. Gerankt wird nach dem Durchschnitt, gewichtet mit der Stimmenzahl (`MIN_VOTES = 5` in `animem/services.py`), damit eine einzelne 10 nicht automatisch gewinnt. „Aktuell beliebt“ zählt die letzten 14 Tage (`TREND_DAYS`): neue Bewertung = 3 Punkte, als gesehen markierte Folge = 1 Punkt.
- **Bestehende Datenbank:** Wird beim Start automatisch auf das neue Schema gebracht (alte Serien-Bewertungen zählen danach für Staffel 1). Vorher am besten `data/animem.db` kopieren.

## Streams, Sprachen, Import, Benachrichtigungen, Entdecken

- **Sprach-Labels (GerDub / GerSub / OmU):** Jeder Stream hat eine Sprache. Im Player gibt es Sprach-Chips zum Filtern. Die gewählte Sprache wird gemerkt (mit Konto im Profil, sonst im Browser) und beim nächsten Mal vorausgewählt. Gibt es in der Wunschsprache keinen funktionierenden Stream, startet automatisch ein anderer.
- **Defekte Links:** Im Player gibt es „⏭ Nächster Anbieter“ und „⚠ Stream defekt“ (meldet den Stream und springt zum nächsten Anbieter). Die Meldungen landen unter `/admin/reports` (Zähler pro Stream, Aktionen: Erledigt / Ignorieren / Stream entfernen / Jetzt prüfen). Wird ein Link im Editor ersetzt, schließt sich die Meldung automatisch.
- **Automatischer Link-Check:** Läuft alle `LINKCHECK_INTERVAL_HOURS` Stunden (Standard 24, `0` = aus) im Hintergrund und per Knopf im Admin oder mit `python manage.py check-links` (z. B. per Cron). Erst nach **2 Fehlschlägen in Folge** gilt ein Link als tot (vorher „verdächtig“). Anbieter, die Automaten blockieren (403/429), werden **nicht** als tot gewertet. Tote Links stehen im Player hinten und sind als „evtl. offline“ markiert. Hinweis: Manche Hosts liefern auch für gelöschte Videos „200 OK“ – der Check erkennt typische „Datei gelöscht“-Texte, kann aber nicht alles finden.
- **Metadaten-Import:** Im Serien-/Film-Editor unter „Metadaten importieren“ (AniList oder Jikan/MyAnimeList) Titel suchen und übernehmen: Titel, Beschreibung, Cover, Genres, Tags, Zweittitel, Jahr, Status und bei Serien **alle Staffeln** (Prequel/Sequel-Kette) mit Folgenliste, Staffel-Bildern und – falls bekannt – Erscheinungsdaten. Folgen ohne Stream gelten als „angekündigt“. Streams trägst du danach ein, am schnellsten mit den **Massen-Funktionen** je Staffel (Folgen 1–12 anlegen; viele Links einer Sprache auf einmal eintragen).
- **Benachrichtigungen:** Für abonnierte Serien (Glocke oben rechts + `/notifications`). Pro Nutzer einstellbar, **für welche Sprachen** man informiert werden will (Profil), zusätzlich pro Serie (eigene Auswahl oder stumm). Beispiel: Nur „GerDub“ → keine Meldung, wenn Staffel 2 zuerst nur mit Untertiteln erscheint; sobald die Synchro dazukommt, kommt „Staffel 2 ist jetzt verfügbar (GerDub …)“. Arten: neue Staffel, neue Folge, bereits vorhandene Folge jetzt auch in einer weiteren Sprache (abschaltbar). Mehrfaches Speichern erzeugt keine doppelten Meldungen.
- **Entdecken:** Serienliste mit Filtern (Genre, Jahr, Sprache, Status) und Sortierung (zuletzt aktualisiert, neu, Bewertung, A–Z), Seiten à 24; Suche findet auch **Zweittitel** (Akzente/Satzzeichen egal); Startseite mit „Zuletzt aktualisiert“ (inkl. Notiz zur neuesten Folge) und „Demnächst & neu“; **Erscheinungskalender** (`/calendar`, auch nur für die eigenen Serien); „Ähnliche Serien“ auf der Serienseite (gleiche Genres/Tags/Jahr).
- **Bestehende Datenbank:** Wird beim Start automatisch erweitert. Alte Streams ohne Sprache bekommen „OmU“ und lassen sich im Editor korrigieren.
- **Hinweis zu AniList/Jikan:** Der Import braucht Internet auf dem Server. Er wurde hier mit nachgestellten Antworten getestet, nicht gegen die echten Dienste – falls die Dienste ihre Antwortformate ändern, zeigt der Editor eine Fehlermeldung statt abzustürzen.

## Kostenloser Test-Server auf Render (zum Bug-Suchen)

Im Free-Plan gibt es **keine Persistent Disk und keine Shell**: Datenbank und Uploads werden bei jedem Neustart/Deploy geleert (und nach ~15 Min Leerlauf schläft der Dienst ein, der erste Aufruf dauert dann ~1 Minute). Zum Testen ist das okay.

1. Render → **New → Web Service** (nicht „Blueprint“, die `render.yaml` ist für den bezahlten Plan mit Disk) → Repository wählen. `app.py` und `requirements.txt` müssen im **Wurzelverzeichnis** des Repos liegen.
2. Einstellungen:
   - Runtime: **Python 3**, Instance Type: **Free**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`
   - Health Check Path: `/api/health`
3. Environment Variables:
   - `PYTHON_VERSION` = `3.12.3`
   - `TRUST_PROXY` = `1`
   - `OWNER_EMAIL` = deine E-Mail
   - `OWNER_USERNAME` = dein Benutzername (optional, zusätzlicher Schutz)
   - `OWNER_AUTO_PROMOTE` = `1` → **das erste Konto, das sich mit genau dieser E-Mail registriert, wird automatisch Owner** (nötig, weil es keine Shell für `make-owner` gibt). Nur für Test-Server; auf einem echten Server weglassen und `manage.py make-owner` benutzen.
4. Nach jedem Neustart: neu registrieren → du bist Owner → Testdaten wieder anlegen.

Fehler findest du unter **Render → Logs** (jeder 500er schreibt den vollständigen Traceback dorthin).

## Umgebungsvariablen

`ANIMEM_DB_PATH`, `ANIMEM_STORAGE_DIR`, `OWNER_EMAIL`, `OWNER_USERNAME`, `OWNER_AUTO_PROMOTE`, `LINKCHECK_INTERVAL_HOURS`, `TRUST_PROXY`, `PORT`, `HOST` – siehe `.env.example`.

## Was sich gegenüber der Next.js-Version geändert hat

**Behoben / verbessert**
- Das Forum war nicht benutzbar, weil es keine Möglichkeit gab, Kategorien anzulegen → Standardkategorien + Verwaltung unter `/admin/forum`.
- Die Einstellungen „Registrierung offen“ und „Wartungsmodus“ hatten keine Wirkung → werden jetzt durchgesetzt.
- Genre-/Tag-Seiten zeigten auch Entwürfe → nur noch veröffentlichte Titel.
- 2FA-Einrichtung konnte bei aktiver 2FA ohne Code zurückgesetzt werden → jetzt gesperrt (erst deaktivieren).
- Client-IP wurde blind aus `X-Forwarded-For` gelesen (fälschbar) → nur mit `TRUST_PROXY=1`.
- Gesperrte Nutzer werden sofort abgemeldet; Umnummerieren/Tauschen von Folgen scheitert nicht mehr an UNIQUE-Regeln.
- Löschen einer Serie entfernt auch Bewertungen/Verlauf ihrer Folgen.
- „Nächste Folge“ springt am Staffelende in die nächste Staffel.
- Support: Antwort des Nutzers öffnet ein „gelöstes“ Ticket wieder.

**Bewusst anders**
- Passwort-Hashes der alten bcrypt-Datenbank sind nicht übernehmbar; alte PostgreSQL-Daten werden nicht automatisch importiert.
- Genres/Tags/Streams im Admin-Editor sind eine eigene Seite (`/admin/series/new`) statt Modal.
- 2FA: statt QR-Code gibt es einen Link, der direkt die Authenticator-App öffnet (praktisch auf dem Handy), plus den Schlüssel zum Abtippen.
