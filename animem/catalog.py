"""Entdecken: Filter, Suche (auch Zweittitel), Sortierung, Ähnliche Serien, Erscheinungskalender."""
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from . import db, langs, services

PAGE_SIZE = 24
SORTS = [("updated", "Zuletzt aktualisiert"), ("new", "Neu hinzugefügt"), ("rating", "Beste Wertung"), ("az", "A–Z")]
STATUS_LABELS = {"AIRING": "Läuft aktuell", "FINISHED": "Abgeschlossen", "UPCOMING": "Angekündigt", "HIATUS": "Pausiert", "CANCELLED": "Abgebrochen"}


def norm(text):
    """Klein, ohne Akzente/Satzzeichen – 'Shingeki no Kyojin: The Final' == 'shingeki no kyojin the final'."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def search_text(record):
    return norm(" ".join([record["title"], *(record.get("alt_titles") or [])]))


def matches(record, query):
    tokens = norm(query).split()
    if not tokens:
        return True
    hay = search_text(record)
    return all(t in hay for t in tokens)


def title_hit(record, query):
    """Passender Zweittitel (nur wenn der Haupttitel nicht schon passt) – für die Anzeige 'auch bekannt als …'."""
    if matches({"title": record["title"], "alt_titles": []}, query):
        return ""
    for alt in record.get("alt_titles") or []:
        if matches({"title": alt, "alt_titles": []}, query):
            return alt
    return ""


# ---- Sprachen je Serie -----------------------------------------------------------------------

series_langs = services.series_langs


# ---- Katalog mit Filtern ---------------------------------------------------------------------

def facets():
    series = db.rows("SELECT year, air_status, genre_ids FROM series WHERE status='PUBLISHED'")
    genre_ids = {g for s in series for g in (s["genre_ids"] or [])}
    genres = [g for g in db.rows("SELECT id, name, slug FROM genres ORDER BY name COLLATE NOCASE") if g["id"] in genre_ids]
    years = sorted({s["year"] for s in series if s["year"]}, reverse=True)
    statuses = [(k, STATUS_LABELS[k]) for k in STATUS_LABELS if any(s["air_status"] == k for s in series)]
    return {"genres": genres, "years": years, "statuses": statuses}


def search_series(params, user_id=None):
    """params: dict mit q, genre (Slug), year, lang, status, sort, page. Gibt (Karten, Gesamtzahl, Seite, Seiten) zurück."""
    rows = db.rows("SELECT * FROM series WHERE status='PUBLISHED'")
    q = (params.get("q") or "").strip()
    if q:
        rows = [r for r in rows if matches(r, q)]
    if params.get("genre"):
        g = db.row("SELECT id FROM genres WHERE slug=?", (params["genre"],))
        rows = [r for r in rows if g and g["id"] in (r["genre_ids"] or [])]
    if params.get("year"):
        try:
            y = int(params["year"])
            rows = [r for r in rows if r["year"] == y]
        except ValueError:
            pass
    if params.get("status") in STATUS_LABELS:
        rows = [r for r in rows if r["air_status"] == params["status"]]
    if params.get("lang") in langs.LANGS:
        have = series_langs()
        rows = [r for r in rows if params["lang"] in have.get(r["id"], [])]

    sort = params.get("sort") if params.get("sort") in dict(SORTS) else "updated"
    if sort == "new":
        rows.sort(key=lambda r: r["created"], reverse=True)
    elif sort == "rating":
        rows.sort(key=lambda r: (-(r["avg_rating"] or 0), -(r["ratings_count"] or 0), r["title"].lower()))
    elif sort == "az":
        rows.sort(key=lambda r: norm(r["title"]))
    else:
        rows.sort(key=lambda r: r["content_updated"] or r["created"], reverse=True)

    total = len(rows)
    pages = max(1, -(-total // PAGE_SIZE))
    try:
        page = min(max(1, int(params.get("page") or 1)), pages)
    except ValueError:
        page = 1
    chunk = rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    cards = services.series_cards(chunk, user_id)
    for card, row in zip(cards, chunk):
        card["note"] = row.get("last_update_note", "")
        card["alt_hit"] = title_hit(row, q) if q else ""
    return cards, total, page, pages


# ---- Ähnliche Serien -------------------------------------------------------------------------

def similar_series(series, limit=6, user_id=None):
    """Ähnlichkeit nach gemeinsamen Genres (Gewicht 2), Tags (1) und gleichem Jahr (+0,5). Mindestens ein gemeinsames Genre oder 2 Tags."""
    mine_g, mine_t = set(series["genre_ids"] or []), set(series["tag_ids"] or [])
    scored = []
    for r in db.rows("SELECT * FROM series WHERE status='PUBLISHED' AND id<>?", (series["id"],)):
        g, t = len(mine_g & set(r["genre_ids"] or [])), len(mine_t & set(r["tag_ids"] or []))
        if not g and t < 2:
            continue
        score = 2 * g + t + (0.5 if series.get("year") and series["year"] == r["year"] else 0)
        scored.append((score, r["avg_rating"] or 0, r))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]["title"].lower()))
    return services.series_cards([r for _s, _a, r in scored[:limit]], user_id)


# ---- Erscheinungskalender --------------------------------------------------------------------

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _day(value):
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def calendar(start, end, user_id=None, mine=False):
    """Folgen mit Erscheinungsdatum im Zeitraum, gruppiert nach Tag. Verfügbar = hat einen Stream, sonst 'angekündigt'."""
    rows = db.rows(
        "SELECT e.id AS eid, e.number AS en, e.title AS et, e.aired_at, e.streams, e.status AS estatus, "
        "se.number AS sn, se.thumbnail_url AS season_thumb, s.id AS sid, s.title, s.slug, s.thumbnail_url AS series_thumb "
        "FROM episodes e JOIN seasons se ON se.id = e.season_id JOIN series s ON s.id = se.series_id "
        "WHERE s.status='PUBLISHED' AND e.aired_at <> '' AND substr(e.aired_at, 1, 10) BETWEEN ? AND ? "
        "ORDER BY e.aired_at, s.title, se.number, e.number", (start.isoformat(), end.isoformat()))
    mine_ids = set()
    if mine and user_id:
        mine_ids = {r["series_id"] for r in db.rows("SELECT series_id FROM subscriptions WHERE user_id=?", (user_id,))}
        mine_ids |= {r["series_id"] for r in db.rows("SELECT series_id FROM watchlist_items WHERE user_id=? AND series_id IS NOT NULL", (user_id,))}
    days = {}
    for r in rows:
        if mine and r["sid"] not in mine_ids:
            continue
        d = _day(r["aired_at"])
        if not d:
            continue
        have = langs.ordered({s.get("lang") for s in (r["streams"] or []) if s.get("lang")}) if r["estatus"] == "PUBLISHED" else []
        days.setdefault(d, []).append({
            "title": r["title"], "season": r["sn"], "episode": r["en"], "episode_title": r["et"],
            "cover": r["season_thumb"] or r["series_thumb"], "available": bool(have), "langs": have,
            "href": f"/series/{r['slug']}/s/{r['sn']}/e/{r['en']}" if have else f"/series/{r['slug']}?season={r['sn']}",
        })
    today = datetime.now(timezone.utc).date()
    out = []
    for d in sorted(days):
        label = f"{WEEKDAYS[d.weekday()]}, {d.day:02d}.{d.month:02d}."
        if d == today:
            label = "Heute · " + label
        elif d == today + timedelta(days=1):
            label = "Morgen · " + label
        out.append({"date": d, "label": label, "today": d == today, "past": d < today, "items": days[d]})
    return out
