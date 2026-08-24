# Animem — Setup-Anleitung (vom Handy, ohne Budget)

Du brauchst am Ende: einen **Codeberg**-Account (Code-Hosting), einen
Ort, an dem **PocketBase** läuft (dein Backend — Datenbank, Login,
Datei-Uploads in einem einzigen kleinen Programm), und einen
Hosting-Anbieter für die fertige Next.js-Seite (z. B. Vercel).

## Schritt 1 — Codeberg-Repo anlegen

1. Gehe im Handy-Browser auf **codeberg.org** → registrieren/einloggen (kostenlos).
2. **+ Neues Repository** → Name z. B. `animem` → erstellen.
3. Projekt-Dateien hochladen (per Weboberfläche oder, falls du wie bisher
   Termux direkt auf dem Handy nutzt, per `git push` von dort aus).

## Schritt 2 — PocketBase zum Laufen bringen

PocketBase ist kein Cloud-Dienst, sondern ein einzelnes, kostenloses
Programm (ca. 15 MB), das irgendwo laufen muss. Drei Wege, die ohne
eigene Kreditkarte funktionieren:

**Option A — Fly.io (empfohlen, kostenloses Kontingent):**
1. Account auf **fly.io** anlegen.
2. Fly bietet ein fertiges PocketBase-Deploy-Template — im Fly-Dashboard
   nach "PocketBase" suchen oder `fly launch` mit dem offiziellen
   PocketBase-Docker-Image (`ghcr.io/muchobien/pocketbase`) verwenden.
3. Nach dem Deploy bekommst du eine URL wie `https://dein-projekt.fly.dev`.

**Option B — Ein kleiner VPS** (z. B. bei einem günstigen Anbieter):
1. PocketBase-Binary von **pocketbase.io/docs** herunterladen (passend zu
   Linux) und auf dem Server ausführen: `./pocketbase serve --http=0.0.0.0:8090`.
2. Am besten dauerhaft laufen lassen (z. B. mit `systemd` oder `pm2`).

**Option C — PikaPods** (pikapods.com): bietet PocketBase als
Ein-Klick-Hosting an, ebenfalls mit kostenlosem Startguthaben.

Wichtig: Notiere dir die **URL deiner PocketBase-Instanz**
(z. B. `https://dein-projekt.fly.dev`).

## Schritt 3 — Admin-Account in PocketBase anlegen

1. Rufe `<deine-pocketbase-url>/_/` im Browser auf.
2. Beim allerersten Aufruf fragt PocketBase nach einer Admin-E-Mail und
   einem Admin-Passwort — das ist dein Superuser-Zugang. Merk ihn dir gut.

## Schritt 4 — Umgebungsvariablen setzen

1. Kopiere `.env.example` zu `.env.local`.
2. Trage deine Werte ein:

   ```
   NEXT_PUBLIC_POCKETBASE_URL=https://dein-projekt.fly.dev
   POCKETBASE_ADMIN_EMAIL=admin@example.com
   POCKETBASE_ADMIN_PASSWORD=dein-admin-passwort
   ```

## Schritt 5 — Datenbank automatisch anlegen

Im Terminal (Termux, Gitpod-Workspace o. Ä.) im Projektordner:

```
npm install
node scripts/pocketbase-setup.mjs
```

Das Skript legt automatisch an: alle 20 Collections mit Feldern/Indizes
(Serien, Staffeln, Episoden, Filme, Ratings, Watchlist, Abos, Forum,
Tickets, Sieger-Treppchen, …), erweitert die eingebaute `users`-Collection
um die Profilfelder (username, role, avatar_url, bio, …) und legt die
`uploads`-Collection für Bild-Uploads an. Es kann gefahrlos mehrfach
ausgeführt werden — bereits Vorhandenes wird übersprungen.

## Schritt 6 — Lokal starten

```
npm run dev
```

Der erste registrierte Account bekommt keine Sonderrolle automatisch —
setze dich selbst als Owner: gehe in die PocketBase-Admin-Oberfläche
(`<deine-pocketbase-url>/_/`) → Collections → `users` → dein Konto
suchen → Feld `role` auf `OWNER` setzen. Danach kannst du im
Admin-Bereich der Seite weitere Rollen vergeben.

## Schritt 7 — Deployment der Next.js-Seite

1. Gehe auf **vercel.com** → registrieren.
2. Da Vercel primär GitHub/GitLab/Bitbucket-Import unterstützt, importiere
   das Projekt entweder per **manuellem Upload der Projektdateien** oder
   verbinde einen GitHub-Spiegel deines Codeberg-Repos (Codeberg →
   Repo-Einstellungen → Mirror). Alternativ eignet sich jeder andere
   Next.js-fähige Host, der direktes Repo-Hochladen erlaubt.
3. Trage dieselben Umgebungsvariablen aus `.env.local` in den
   Projekteinstellungen des Hosters ein.
4. Deployen — fertig. PocketBase läuft weiterhin separat auf Fly.io/VPS/PikaPods.

## Checkliste

- [ ] Codeberg-Repo erstellt, Code hochgeladen
- [ ] PocketBase gehostet (Fly.io / VPS / PikaPods), URL notiert
- [ ] Admin-Account in PocketBase angelegt
- [ ] `.env.local` ausgefüllt
- [ ] `node scripts/pocketbase-setup.mjs` erfolgreich durchgelaufen
- [ ] Eigenen Account als `OWNER` gesetzt (in der PocketBase-Admin-UI)
- [ ] Next.js-Deployment eingerichtet
