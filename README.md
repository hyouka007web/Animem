# TUF-Blade Browser — Starter-Projekt

Android-Studio-Projekt (Kotlin + GeckoView), aufgebaut exakt nach `design.md`
(Farben/Typografie/Spacing/Layout 1:1 als Ressourcen übernommen).

## Was drin ist (funktionsfähig)

- **GeckoView-Integration** (`TufBladeApp.kt`, `MainActivity.kt`) — Basis-Browser mit URL-Feld, lädt Seiten.
- **AdBlocker, 2 Ebenen** (wie klassische Adblock-Browser):
  1. Geckos natives `ContentBlocking` (Tracking/Ads/Fingerprinting/Cryptomining, Resource-Ebene) — `TufBladeApp.kt`
  2. Eigene Host-/Pattern-Sperrliste (EasyList-Syntax, Beispiel-Liste unter `assets/blocklist_hosts.txt`) — `AdBlockEngine.kt`
- **Redirect-Shield** (`RedirectShield.kt`): blockt Popups (`window.open`) und Domain-fremde Weiterleitungen ohne Nutzeraktion, mit "trotzdem öffnen"-Option statt stillem Verschwinden.
- **Design-Tokens** (`colors.xml`, `dimens.xml`, `themes.xml`) 1:1 aus `design.md`.
- **Layout-Grundgerüst**: Top Bar + Sidebar-Streifen + Content-Container + Sniffer-Panel-Platzhalter, exakt die Struktur aus design.md Abschnitt 5.
- **Chaquopy** ist im Gradle-Setup eingebunden, mit `yt-dlp` und `scrapling` als Pip-Dependencies vorkonfiguriert (siehe `app/build.gradle.kts`) — noch nicht an die UI angebunden.

## Was als TODO markiert / noch nicht gebaut ist

Ehrlich gesagt: ein "kompletter Browser" mit allen Features aus dem
Gesamtkonzept ist in einem Rutsch nicht seriös baubar — hier ist ein
funktionierendes Fundament mit den zwei explizit gewünschten Kern-Features
(Adblock + Redirect-Shield), auf dem wir jetzt modulweise draufbauen:

- [ ] Sidebar ausklappbar mit Web-App-Icons (aktuell nur der Farbstreifen)
- [ ] Tab-Verwaltung (Multi-Tab, aktuell nur eine Session)
- [ ] Scrapling Split View (Panel-UI + Anbindung ans Chaquopy-Python-Backend)
- [ ] Media-Sniffer + Mediathek
- [ ] Chaquopy-Python-Aufrufe aus Kotlin (`Python.getInstance().getModule(...)`) für yt-dlp/Scrapling
- [ ] Orbot-Anbindung für Tor-Routing im Inkognito-Modus
- [ ] Vollständige EasyList/EasyPrivacy statt der Beispiel-Sperrliste
- [ ] Custom-CSS-Injektor, User-Agent-Spoofer-UI, Einstellungs-Dashboard

## Setup

1. Android Studio (aktuelle Version) öffnen → "Open" → diesen Ordner wählen.
2. Gradle-Sync abwarten (lädt GeckoView + Chaquopy-Dependencies).
3. Auf echtem Gerät oder Emulator (API 26+) ausführen.
4. Falls die GeckoView-Version-Nummer in `app/build.gradle.kts` veraltet ist:
   aktuelle Version unter https://maven.mozilla.org/maven2/org/mozilla/geckoview/ nachsehen.

## Nächster Schritt

Sag mir, welches TODO-Modul als Nächstes drankommt (z. B. Sidebar mit
Web-Apps, oder direkt die Scrapling/Chaquopy-Anbindung) — dann bauen wir
darauf weiter, immer gegen `design.md` abgeglichen.
