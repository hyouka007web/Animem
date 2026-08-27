# Security Policy

## Sicherheitsgrundsätze

Animem behandelt PocketBase-Admin-Zugriff ausschließlich serverseitig. Der Browser erhält keine Admin-Credentials und verwendet keine direkte PocketBase-Schreib-API.

### Geschützt

- HttpOnly/SameSite-Session-Cookie
- serverseitige Authentifizierung und Rollenprüfung
- serverseitige Prüfung von `is_banned`
- Zod-Validierung für API-Eingaben
- Rate-Limits für sensible Endpunkte
- Sicherheitsheader + CSP in Produktion
- HTTPS-Pflicht für PocketBase und Media-URLs in Produktion
- Upload-MIME-, Größen- und Magic-Byte-Prüfung
- Unique-Indizes für kritische Benutzer-/Ziel-Beziehungen
- Prüfung von Serie → Staffel → Episode bei Admin-Änderungen

## Betrieb

Rate-Limiting in `src/lib/security.ts` ist pro Node-Prozess. Für mehrere Instanzen sollte zusätzlich ein zentraler Limiter/WAF auf Render oder vor dem Reverse Proxy aktiviert werden.

PocketBase-Admin-Credentials gehören ausschließlich in die Secret-Verwaltung des Hosters.

## Meldung von Sicherheitsproblemen

Bitte keine öffentlich ausnutzbaren Details in einem normalen Issue veröffentlichen. Bei einem produktiven Einsatz sollte ein privater Security-Kontakt bzw. ein privates Advisory-Verfahren eingerichtet werden.
