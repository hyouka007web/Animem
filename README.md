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

## Umgebungsvariablen

`ANIMEM_DB_PATH`, `ANIMEM_STORAGE_DIR`, `OWNER_EMAIL`, `OWNER_USERNAME`, `TRUST_PROXY`, `PORT`, `HOST` – siehe `.env.example`.

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
