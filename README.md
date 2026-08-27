# Animem

Animem ist eine Next.js-14-Anwendung mit PocketBase als Backend für Anime-Serien, Filme, Watchlist, Bewertungen, Profile, Forum und Support-Tickets.

## Architektur

- Next.js App Router + React 18
- PocketBase für Auth, Daten und Dateispeicher
- Sensible Datenbankoperationen ausschließlich über serverseitige Next.js-APIs
- Rollen: USER, ADMIN, HEAD_ADMIN, OWNER
- Keine statische Export-Ausgabe

## Lokale Einrichtung

1. `.env.example` nach `.env.local` kopieren.
2. Eine frische PocketBase-Instanz verwenden.
3. `NEXT_PUBLIC_POCKETBASE_URL`, `POCKETBASE_ADMIN_EMAIL` und `POCKETBASE_ADMIN_PASSWORD` setzen.
4. Für externe Bilder `ANIMEM_IMAGE_HOSTS` als komma-getrennte HTTPS-Hostnamen setzen. Der PocketBase-Host wird automatisch erlaubt.
5. `npm install` ausführen.
6. `node scripts/pocketbase-setup.mjs` ausführen.
7. `npm run dev` starten.

## Produktion / Render

Der mitgelieferte `render.yaml` verwendet bewusst npm statt Yarn:

```text
Build: npm install --no-audit --no-fund && npm run build
Start: npm start
```

Node 20 wird über `.nvmrc` und `package.json` vorgegeben. Für Render müssen die vier Variablen aus `.env.example` als Secret/Environment Variables gesetzt werden.

## Sicherheit

- Auth-Session liegt als `HttpOnly`, `SameSite=Lax` Cookie vor.
- Gebannte Benutzer werden serverseitig abgewiesen.
- Rollen werden niemals aus Browser-Eingaben übernommen.
- API-Eingaben werden mit Zod validiert.
- Mutierende Endpunkte besitzen Rate-Limits.
- Uploads laufen über `/api/uploads`, nicht mehr direkt über die PocketBase-API.
- Uploads sind auf PNG/JPEG/WebP/GIF und 10 MB begrenzt.
- Sicherheitsheader werden zentral per Middleware gesetzt.
- Remote-Bilder sind auf HTTPS-Hosts beschränkt.
- Admin- und Benutzer-Daten sind über PocketBase-Regeln nicht direkt öffentlich schreibbar.
- Serien-/Staffel-/Episoden-Beziehungen werden bei Änderungen serverseitig verifiziert.
- Ratings, Watchlists, Abos und Profil-Favoriten werden durch Unique-Indizes gegen Duplikate geschützt.

## Daten und Backups

`pb_data/` enthält Benutzer, Sessions und Runtime-Daten und gehört nicht in Git. Backups der PocketBase-Daten müssen getrennt und verschlüsselt aufbewahrt werden.

## Qualitätssicherung

```bash
npm run typecheck
npm run build
npm run security:check
```

Die GitHub-CI führt Installation, TypeScript-Prüfung und einen Produktions-Build aus. Der frühere fremde Android/APK-Workflow wurde entfernt.
