# Animem

Animem ist eine Next.js-14-Anwendung mit PocketBase als Backend.

## Architektur

- Next.js App Router (Node.js Server)
- PocketBase als Datenbank/Auth/Dateispeicher
- Server-seitige Admin-API für sensible Datenbankoperationen
- Keine statische `output: export`-Ausgabe

## Lokale Einrichtung

1. `.env.example` nach `.env.local` kopieren und die echten PocketBase-Werte eintragen.
2. Eine **frische** PocketBase-Instanz verwenden. Die alte `pb_data/`-Datenbank gehört zu einem inkompatiblen Legacy-Schema und wird absichtlich nicht mit dem Projekt versioniert.
3. `node scripts/pocketbase-setup.mjs` ausführen.
4. `npm install` ausführen. Dadurch wird ein neuer, zum bereinigten `package.json` passender `package-lock.json` erzeugt.
5. `npm run dev` starten.

## Daten und Benutzerinformationen

`pb_data/` enthält die echte PocketBase-Datenbank, Benutzerkonten, Sessions/Runtime-Daten und Logs. Diese Daten gehören **nicht** in GitHub. Für Backups sollte die komplette PocketBase-Datenablage außerhalb des Quellcode-Repositories gesichert werden, mit restriktiven Dateirechten und verschlüsseltem Backup.

`.env.local` enthält Server-Geheimnisse und wird ebenfalls nicht versioniert. Verwende GitHub Secrets bzw. die Secret-Verwaltung des jeweiligen Hosters für Deployment.

## Sicherheit

Neue Benutzer werden ausschließlich über `/api/auth/register` angelegt und serverseitig immer mit `role: USER` erstellt. Rollenänderungen laufen über die geschützte Admin-API. Ticket-Nachrichten prüfen die Ticket-Zugehörigkeit.
