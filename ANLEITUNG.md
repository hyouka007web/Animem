# Animem – aktuelle Betriebsanleitung

## 1. Voraussetzungen

- Node.js 20
- npm 10+
- PocketBase 0.21.x / das im Projekt getestete Schemaformat

## 2. Umgebungsvariablen

```env
NEXT_PUBLIC_POCKETBASE_URL=https://dein-pocketbase-host
POCKETBASE_ADMIN_EMAIL=...
POCKETBASE_ADMIN_PASSWORD=...
ANIMEM_IMAGE_HOSTS=cdn.example.com,images.example.com
```

`POCKETBASE_ADMIN_*` darf niemals mit `NEXT_PUBLIC_` beginnen und niemals in den Browsercode gelangen.

## 3. PocketBase einrichten

Für eine neue Instanz:

```bash
npm install
node scripts/pocketbase-setup.mjs
```

Das Setup erstellt bzw. aktualisiert die Animem-Collections, Regeln und wichtigen Unique-Indizes. Bei bereits vorhandenen Legacy-Daten vor dem Einsatz ein Backup erstellen.

## 4. Entwicklung

```bash
npm run dev
```

## 5. Produktionsprüfung

```bash
npm run typecheck
npm run build
npm run security:check
npm start
```

## 6. Render

Nicht `yarn start` verwenden. Das Projekt ist auf npm standardisiert:

- Build: `npm install --no-audit --no-fund && npm run build`
- Start: `npm start`
- Node: 20

`render.yaml` kann als Ausgangspunkt für den Service verwendet werden.

## 7. Sicherheitsregeln

- Keine echten `.env.local`-Dateien committen.
- Keine PocketBase-Admin-Credentials in Clientcode verwenden.
- Keine offenen `http://`-Media-URLs in Produktionsdaten verwenden.
- `ANIMEM_IMAGE_HOSTS` nur mit vertrauenswürdigen HTTPS-Domains befüllen.
- Rate-Limits auf Plattform-/WAF-Ebene zusätzlich aktivieren, weil der eingebaute Limiter pro Node-Prozess arbeitet.
- PocketBase regelmäßig sichern und aktualisieren, nachdem die Kompatibilität des Schemas geprüft wurde.
