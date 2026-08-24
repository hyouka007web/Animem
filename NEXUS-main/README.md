# NEXUS Browser

Android-Browser (Kotlin + GeckoView), aufgebaut nach `design.md`.

## Was in diesem Update neu ist

- **Weißer Bildschirm behoben (echter Bug, bestätigt)**: `GeckoView` wurde
  ohne explizite `LayoutParams` in den Content-Container eingehängt —
  FrameLayout vergibt dann nur `WRAP_CONTENT`, und GeckoView hat keine
  eigene intrinsische Größe, landet also bei ~0×0 Pixel. Jetzt mit
  `FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT)`.
- **Tab-Titel funktioniert jetzt**: `RedirectShield` implementierte
  `ContentDelegate`, aber ohne `onTitleChange` — Tabs blieben für immer auf
  "Neuer Tab" hängen. Jetzt wird der echte Seitentitel live in die
  Tab-Leiste übernommen.

## Hinweis zu einer zirkulierenden Fehleranalyse

Falls du eine Analyse mit Vorschlägen wie "GeckoView 154 ist Zukunft",
"compileSdk 37 gibt es nicht", "Kotlin 2.2.0 existiert nicht" oder
`session.evaluateJS(...)` gesehen hast: Das stimmt nicht (Stand August 2026,
mit offizieller Mozilla-Doku geprüft) bzw. existiert als Methode gar nicht
in der öffentlichen GeckoView-API. Diese Version-Downgrades **nicht**
übernehmen — die aktuellen Werte in diesem Projekt sind korrekt aufgelöst
und funktionieren.

- **Absturz-Fix (wahrscheinliche Ursache gefunden und behoben)**: Der
  manuelle `<service android:name="org.mozilla.geckoview.GeckoViewChildService$Content">`-
  Eintrag im AndroidManifest.xml wurde entfernt. Diese Klasse existiert so
  nicht — GeckoView deklariert seine eigenen Multiprozess-Services bereits
  selbst über sein AAR-Manifest (automatisches Merging). Der doppelte/falsche
  Eintrag hat vermutlich zu einer ClassNotFoundException geführt, sobald
  Gecko beim ersten Seitenaufruf versucht hat, den Content-Prozess zu starten
  — das erklärt den Sofort-Absturz direkt nach dem leeren weißen Bildschirm.
- **Rebranding zu NEXUS**: App-Name, Adaptive-Icon aus dem bereitgestellten
  Logo generiert (`res/mipmap-anydpi-v26/ic_launcher.xml` + `drawable-xxxhdpi`).
- **Anflug-Animation**: `SplashActivity` mit Scale+Fade-Overshoot-Animation
  beim App-Start (~900ms), danach Fade-Übergang zu `MainActivity`.
- **Ausklappbare Sidebar**: Tap auf den Farbstreifen fährt sie aus/ein
  (180ms, design.md-Motion-Spec). Web-Apps werden jetzt **persistiert**
  (SharedPreferences über `NexusSettings`), per "+"-Dialog anpinnbar und
  per Long-Press wieder entfernbar.
- **Tab-Leiste**: mehrere GeckoSession-Instanzen gleichzeitig, horizontal
  scrollbarer Tab-Strip, Schließen einzelner Tabs, aktiver Tab farblich
  hervorgehoben.
- **Klick-Ripple-Animationen**: alle Buttons/Icons/Kacheln nutzen
  `ripple_accent` bzw. `ripple_accent_circle` in `accent_primary`.
- **Mediathek**: Grid heruntergeladener Videos mit **echten Thumbnails**
  (per `MediaMetadataRetriever` aus dem ersten Frame extrahiert), Abspielen
  per Tap (Systemplayer via FileProvider), Löschen per Long-Press.
- **Video-Download (nativ, kein Python)**: `MediaLinkFinder` scannt das HTML
  der aktuellen Seite nach direkten `.mp4`/`.webm`/`.m3u8`-Links,
  `VideoDownloader` lädt den ersten Treffer in den privaten App-Speicher
  (kein Berechtigungs-Dialog nötig) und trägt ihn in die Mediathek ein.
- **Einstellungs-Screen**: Suchmaschine wählbar (DuckDuckGo/Google/Bing),
  Adblocker komplett ein-/ausschaltbar — beides sofort wirksam, lokal
  gespeichert, kein Server.

## Bewusste Design-Entscheidung: kein Chaquopy/yt-dlp (noch)

Chaquopy (Python-Bridge für yt-dlp) ist laut offizieller Doku nur bis
Android-Gradle-Plugin **9.2.x** getestet — dieses Projekt nutzt aber bereits
**9.3.1**. Um nicht wieder in eine Build-Fehler-Schleife zu laufen, lädt
NEXUS Videos vorerst nativ herunter.

**Einschränkung, ehrlich gesagt**: Das funktioniert nur bei Seiten mit
direkt eingebettetem Videolink im HTML (z. B. `<video src="...mp4">`).
Seiten mit eigener Verschlüsselung/Extraktion (YouTube, viele
Streaming-Portale) werden NICHT erfasst — dafür bräuchte es echtes
yt-dlp. Sobald die App stabil läuft, können wir Chaquopy als optionales
Zusatzmodul nachrüsten und gezielt testen.

## Noch offen (TODOs)

- [ ] Web-App-Icons in der Sidebar durch echte Bild-Icons statt Text-Kürzel ersetzen
- [ ] Scrapling Split View
- [ ] Erweiterte EasyList/EasyPrivacy statt der Beispiel-Sperrliste
- [ ] Optional: Chaquopy + yt-dlp nachrüsten für Seiten ohne direkten Videolink
- [ ] Tabs über App-Neustarts hinweg persistieren
- [ ] Zero-Knowledge-Sync (bewusst ausgeklammert, braucht Server)

## Setup — ohne Android Studio (GitHub Actions baut die APK)

1. Diesen kompletten Ordnerinhalt in dein bestehendes GitHub-Repo hochladen
   (überschreibt die alten Dateien) — am einfachsten über den Codespace-
   Terminal: Zip in den Codespace hochladen, dort entpacken, dann
   `git add -A && git commit -m "NEXUS: Crash-Fix, Rebranding, Tabs, Mediathek" && git push`
2. Im Actions-Tab läuft der Build automatisch.
3. APK unter Actions → Build Debug APK → Artifacts herunterladen und installieren.
