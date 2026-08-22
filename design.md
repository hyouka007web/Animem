# TUF-Blade Browser — Design System

Referenz-Dokument für UI/UX. Basis: ASUS-TUF-Gaming-Ästhetik + Dev-Tool-Funktionalität, Android-Zielplattform (Kotlin + GeckoView), Dark-Mode-only.

---

## 1. Farbpalette

| Rolle | Hex | Verwendung |
|---|---|---|
| `bg-base` | `#1E1E1E` | App-Hintergrund, tiefste Ebene |
| `bg-surface` | `#2E3033` | Panels, Sidebar, Karten, Toolbars |
| `bg-surface-raised` | `#3A3D40` | Hover-Zustand von Panels, aktive Tabs |
| `accent-primary` | `#FFB800` | TUF-Gelb — primäre Aktionen, aktive Zustände, Fokus-Ring |
| `accent-success` | `#00FF66` | TUF-Neon-Grün — Status "läuft/fertig", Download abgeschlossen, aktive Verbindung |
| `accent-danger` | `#FF3B3B` | Fehler, Blockiert, Löschen |
| `text-primary` | `#FFFFFF` | Haupttext, Icons aktiv |
| `text-muted` | `#A0A0A0` | Sekundärtext, inaktive Icons, Platzhalter |
| `border-hairline` | `#3F4245` | Trennlinien, Panel-Rahmen (1px) |

**Kontrastregel:** `accent-primary` und `accent-success` nur für Text/Icons ab 18px oder als Fläche mit `text-primary`/`bg-base` als Gegenfarbe verwenden — nie Gelb-auf-Weiß oder Grün-auf-Weiß (Kontrast zu niedrig).

---

## 2. Typografie

Drei Rollen, bewusst technisch/gaming statt neutral:

| Rolle | Font | Einsatz |
|---|---|---|
| **Display** | *Chakra Petch* (Bold/SemiBold) | Sidebar-Titel, Panel-Header, Onboarding — kantige, technische Anmutung passend zum TUF-Look |
| **UI/Body** | *Inter* (Regular/Medium) | Menüs, Einstellungen, Fließtext, Buttons — hohe Lesbarkeit bei kleinen Größen |
| **Mono** | *JetBrains Mono* | Scrapling-Code-Ausgabe, URLs, extrahierte Links, DevTools-Panel |

**Type-Scale (sp/dp, Android):**
- Display L — 28 / SemiBold (Sidebar-App-Namen, Onboarding-Titel)
- Display M — 20 / SemiBold (Panel-Header: "Scrapling Suite", "Videothek")
- Body — 15 / Regular (Standardtext)
- Body Bold — 15 / Medium (Aktive Menüpunkte, Labels)
- Caption — 12 / Regular, `text-muted` (Metadaten, Timestamps, Dateigrößen)
- Mono — 13 / Regular (Code, Selektoren, Links)

---

## 3. Spacing & Radius

- Grid-Basis: **4dp**
- Standard-Abstände: 4 / 8 / 12 / 16 / 24 / 32
- Radius: `4dp` für Buttons/Inputs, `8dp` für Panels/Karten, `0dp` für Sidebar (kantig, TUF-typisch) und Trennlinien
- Panel-Padding: 16dp; Listenzeilen-Höhe: 48dp (Touch-Target-Minimum)

---

## 4. Signatur-Element: Circuit-Trace-Linien

Ein wiederkehrendes visuelles Motiv, das den Dev/Hardware-Charakter trägt: dünne (1–2px) `accent-primary`-Linien mit rechtwinkligen Knicken (wie PCB-Leiterbahnen), die als:
- Unterstreichung unter aktiven Panel-Headern erscheinen (Linie läuft horizontal, macht einen 90°-Knick nach unten zu einem kleinen Punkt/Node),
- Trennung zwischen Sidebar und Hauptcontent statt einer schlichten Linie,
- Ladeanimation im Scrapling-Panel (Linie "zeichnet sich" während des Ladens entlang des Pfads).

Das ist das einzige dekorative Element — ansonsten bleibt die UI flach und funktional, keine Schatten-Verläufe, keine Farbverläufe.

---

## 5. Layout-Struktur

```
┌─────────────────────────────────────────┐
│  Top Bar: URL-Feld · Tabs · Menü (⋮)     │  56dp, bg-surface
├──┬──────────────────────────────────────┤
│  │                                       │
│S │                                       │
│i │        Web-Content (GeckoView)        │
│d │                                       │
│e │                                       │
│b │                                       │
│a │                                       │
│r │                                       │
├──┴──────────────────────────────────────┤
│  Floating Sniffer-Panel (bei Erkennung)  │  auto-height, überlagert unten
└─────────────────────────────────────────┘
```

- **Sidebar**: eingeklappt 4dp schmaler Streifen (nur `accent-primary`-Akzentlinie sichtbar), ausgefahren 72dp (Icon-only) bis 220dp (mit Labels) je nach Geräte-/Tablet-Breite. Web-App-Icons quadratisch, 40dp, `bg-surface-raised` bei aktivem Tab.
- **Top Bar**: URL-Feld links (Mono-Font für die URL selbst), Tab-Strip mittig scrollbar, Hauptmenü (⋮) rechts.
- **Scrapling Split View**: 50/50 vertikal teilbar (Drag-Handle in `accent-primary`), links Seite, rechts Code/Link-Panel mit Tabs (Clean HTML / Python-Code / Medien & Links).
- **Sniffer-Floating-Panel**: erscheint oben, nicht modal — halbtransparenter `bg-surface` mit Suchleiste, max. 3 Zeilen sichtbar, danach scrollbar.
- **Mediathek**: Grid-Layout, Kacheln 2:1 (Thumbnail + Titel + Tag-Chips unten), `bg-surface-raised` beim Long-Press (Kontextmenü: Löschen, Umbenennen, Tag zuweisen).

---

## 6. Komponenten-States

| Element | Default | Hover/Press | Aktiv | Disabled |
|---|---|---|---|---|
| Primärer Button | `bg-surface`, Text weiß, Border `accent-primary` 1px | `bg-surface-raised` | gefüllt `accent-primary`, Text `#1E1E1E` | Border/Text `text-muted`, 40% Opacity |
| Icon (Sidebar) | `text-muted` | `text-primary` | `accent-primary` + Circuit-Trace-Unterstrich | — |
| Toggle (Einstellungen) | Track `bg-surface-raised`, Knopf `text-muted` | — | Track `accent-primary` 30% Opacity, Knopf `accent-primary` | Track/Knopf `text-muted` 30% |
| Status-Indikator (Sniffer/Download) | — | — | `accent-success` gefüllter Punkt + Pulsieren (dezent, max. 2 Zyklen) | — |
| Fehler-Zustand (blockierte Seite, Downloadfehler) | — | — | `accent-danger` Icon + Caption-Text in `accent-danger` | — |

---

## 7. Motion

- Sidebar Ein-/Ausfahren: 180ms, ease-out
- Sniffer-Panel Einblendung: 220ms slide-down + fade
- Circuit-Trace-Ladeanimation: 400–600ms, linear, einmalig pro Ladevorgang (kein Loop)
- Keine dekorativen Hover-Animationen auf Listenelementen — nur Farbwechsel, kein Scale/Bounce (Performance auf Android priorisieren)
- `Reduced Motion`-Systemeinstellung respektieren: alle Übergänge → sofortiger Zustandswechsel ohne Animation

---

## 8. Accessibility

- Fokus-Ring (Hardware-Tastatur/Controller-Navigation, da "Keyboard-First"-Anspruch): 2px `accent-primary`, 2dp Abstand zum Element
- Mindestkontrast Text/Hintergrund: 4.5:1 (Body), 3:1 (Caption ab 12px nur bei ausreichend fettem Gewicht)
- Touch-Targets minimal 48×48dp, auch im eingeklappten Sidebar-Zustand
- Alle Status-Icons (Sniffer erkannt, Download fertig, Fehler) zusätzlich mit Text-Label, nicht nur Farbe/Icon (Farbenblindheit)

---

## 9. Icon-Stil

Outline-Icons, 2px Strichstärke, keine gefüllten Icons außer im aktiven Zustand (dann `accent-primary` gefüllt). Eckige statt runde Linienenden — passend zur kantigen Radius-0-Sidebar und dem technischen Gesamtbild.
