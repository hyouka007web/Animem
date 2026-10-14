"""Gemeinsame Geschäftslogik: Slugs, Genres/Tags, Anreicherung, Bewertungen, Audit, Tickets."""
import re
import unicodedata

from flask import g, has_app_context, request

from . import db, langs as langs_mod
from .security import client_ip

# ---- Slugs ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return re.sub(r"-+", "-", text).strip("-")


def unique_slug(table: str, title: str, current_id: str | None = None) -> str:
    base = slugify(title) or "item"
    candidate = base
    for i in range(1, 200):
        existing = db.row(f'SELECT id FROM "{table}" WHERE slug=?', (candidate,))
        if not existing or existing["id"] == current_id:
            return candidate
        candidate = f"{base}-{i + 1}"
    raise RuntimeError("Kein eindeutiger Slug konnte erzeugt werden.")


# ---- Genres / Tags -------------------------------------------------------------------


def resolve_taxonomy_ids(table: str, names: list[str]) -> list[str]:
    ids = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        slug = slugify(name) or "item"
        existing = db.row(f'SELECT id FROM "{table}" WHERE slug=?', (slug,))
        if existing:
            if existing["id"] not in ids:
                ids.append(existing["id"])
            continue
        created = db.insert(table, {"name": name, "slug": unique_slug(table, name)})
        ids.append(created["id"])
    return ids


def taxonomy_items(table: str, ids: list[str]) -> list[dict]:
    out = []
    for i in ids or []:
        r = db.get(table, i)
        if r:
            out.append(r)
    return out


def taxonomy_names(table: str, ids: list[str]) -> list[str]:
    return [r["name"] for r in taxonomy_items(table, ids)]


def find_by_taxonomy(table: str, field: str, taxonomy_id: str) -> list[dict]:
    """Alle veröffentlichten Einträge, deren genre_ids/tag_ids die ID enthalten (beste Bewertung zuerst)."""
    items = db.rows(f'SELECT * FROM "{table}" WHERE status=\'PUBLISHED\' ORDER BY avg_rating DESC, title')
    return [i for i in items if taxonomy_id in (i.get(field) or [])]


# ---- Anreicherung --------------------------------------------------------------------


def enrich_users(records: list[dict], fk: str = "user_id") -> list[dict]:
    ids = list({r[fk] for r in records if r.get(fk)})
    users = {}
    if ids:
        marks = ",".join("?" for _ in ids)
        users = {u["id"]: u for u in db.rows(f"SELECT * FROM users WHERE id IN ({marks})", ids)}
    return [{**r, "user": users.get(r.get(fk))} for r in records]


def enrich_targets(records: list[dict]) -> list[dict]:
    def fetch(table, ids):
        ids = list({i for i in ids if i})
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        return {r["id"]: r for r in db.rows(f'SELECT * FROM "{table}" WHERE id IN ({marks})', ids)}

    series = fetch("series", [r.get("series_id") for r in records])
    movies = fetch("movies", [r.get("movie_id") for r in records])
    out = []
    for r in records:
        extra = {}
        if r.get("series_id"):
            extra["series"] = series.get(r["series_id"])
        if r.get("movie_id"):
            extra["movie"] = movies.get(r["movie_id"])
        out.append({**r, **extra})
    return out


# ---- Serien laden / löschen ------------------------------------------------------------


def load_full_series(series_id: str):
    s = db.get("series", series_id)
    if not s:
        return None
    seasons = db.rows("SELECT * FROM seasons WHERE series_id=? ORDER BY number", (series_id,))
    for season in seasons:
        season["episodes"] = db.rows("SELECT * FROM episodes WHERE season_id=? ORDER BY number", (season["id"],))
    return {
        **s,
        "seasons": seasons,
        "genres": taxonomy_names("genres", s["genre_ids"]),
        "tags": taxonomy_names("tags", s["tag_ids"]),
    }


def recalc_rating(target_type: str, target_id: str):
    field = {"SERIES": "series_id", "MOVIE": "movie_id"}[target_type]
    table = {"SERIES": "series", "MOVIE": "movies"}[target_type]
    r = db.get_db().execute(
        f"SELECT AVG(value) AS avg, COUNT(*) AS n FROM ratings WHERE target_type=? AND {field}=?", (target_type, target_id)
    ).fetchone()
    avg = round(float(r["avg"] or 0), 1)
    db.update(table, target_id, {"avg_rating": avg, "ratings_count": int(r["n"] or 0)})


# ---- Audit ---------------------------------------------------------------------------


def audit(actor_id, action, target_type=None, target_id=None, metadata=None):
    try:
        db.insert("audit_logs", {
            "actor_id": actor_id, "action": action, "target_type": target_type, "target_id": target_id,
            "metadata": metadata or {}, "ip": client_ip(),
            "user_agent": (request.headers.get("User-Agent") or "")[:300] or None,
        })
    except Exception:  # Audit darf nie eine eigentliche Aktion zum Scheitern bringen
        pass


# ---- Tickets -------------------------------------------------------------------------


def cleanup_closed_tickets():
    """Löscht Tickets, die seit mehr als 24 Stunden CLOSED sind (samt Nachrichten per CASCADE)."""
    db.run("DELETE FROM tickets WHERE status='CLOSED' AND updated <= ?", (db.iso_ago(24 * 3600),))


# ======================================================================================
# Staffel-Bewertungen
# ======================================================================================


def recalc_season_rating(season_id: str):
    """Aktualisiert Durchschnitt/Anzahl der Staffel und den Gesamtwert der zugehörigen Serie."""
    r = db.get_db().execute(
        "SELECT AVG(value) AS avg, COUNT(*) AS n FROM ratings WHERE target_type='SEASON' AND season_id=?", (season_id,)
    ).fetchone()
    db.update("seasons", season_id, {"avg_rating": round(float(r["avg"] or 0), 1), "ratings_count": int(r["n"] or 0)})
    season = db.get("seasons", season_id)
    if season:
        recalc_series_rating(season["series_id"])


def recalc_series_rating(series_id: str):
    r = db.get_db().execute(
        "SELECT AVG(r.value) AS avg, COUNT(*) AS n FROM ratings r JOIN seasons s ON s.id = r.season_id "
        "WHERE r.target_type='SEASON' AND s.series_id=?", (series_id,)
    ).fetchone()
    db.update("series", series_id, {"avg_rating": round(float(r["avg"] or 0), 1), "ratings_count": int(r["n"] or 0)})


# ======================================================================================
# Automatisches Tracking: aktuelle Staffel, Status, Fortschritt
# ======================================================================================

WATCH_SECONDS = 180  # Eine Folge gilt nach 3 Minuten als gesehen
WATCH_TOLERANCE = 10  # Server akzeptiert die Meldung ab 170 s (Netzwerk-/Timer-Toleranz)


def progress_for(user_id, series_ids):
    """Fortschritt je Serie: Staffeln mit veröffentlichten Folgen, gesehene Folgen, aktuelle Staffel, Status.

    Aktuelle Staffel = erste Staffel, die noch nicht komplett gesehen ist (noch nie geschaut -> Staffel 1).
    Ist alles gesehen, bleibt die letzte Staffel aktuell. Status: NOT_STARTED / WATCHING / COMPLETED.
    """
    ids = list({i for i in series_ids if i})
    if not ids:
        return {}
    marks = ",".join("?" for _ in ids)
    rows = db.rows(
        "SELECT se.series_id, se.id AS season_id, se.number, se.title, se.thumbnail_url, se.avg_rating, se.ratings_count, "
        "COUNT(e.id) AS total, COUNT(CASE WHEN h.completed = 1 THEN 1 END) AS watched, COUNT(h.id) AS started "
        "FROM seasons se JOIN episodes e ON e.season_id = se.id AND e.status = 'PUBLISHED' "
        "LEFT JOIN watch_history h ON h.episode_id = e.id AND h.user_id = ? AND h.target_type = 'EPISODE' "
        f"WHERE se.series_id IN ({marks}) GROUP BY se.id ORDER BY se.series_id, se.number",
        [user_id or ""] + ids,
    )
    out = {}
    for r in rows:
        out.setdefault(r["series_id"], {"seasons": []})["seasons"].append(r)
    for p in out.values():
        seasons = p["seasons"]
        p["current"] = next((s for s in seasons if s["watched"] < s["total"]), seasons[-1])
        if all(s["watched"] >= s["total"] for s in seasons):
            p["state"] = "COMPLETED"
        elif any(s["started"] > 0 for s in seasons):
            p["state"] = "WATCHING"
        else:
            p["state"] = "NOT_STARTED"
    return out


def series_langs():
    """{series_id: [Sprachen]} – für Sprach-Badges und den Sprachfilter (pro Anfrage zwischengespeichert)."""
    if has_app_context() and "series_langs" in g:
        return g.series_langs
    out = {}
    for r in db.rows(
        "SELECT se.series_id AS sid, e.streams FROM episodes e JOIN seasons se ON se.id = e.season_id "
        "JOIN series s ON s.id = se.series_id WHERE e.status='PUBLISHED' AND s.status='PUBLISHED'"
    ):
        bucket = out.setdefault(r["sid"], set())
        for st in r["streams"] or []:
            if st.get("lang"):
                bucket.add(st["lang"])
    result = {sid: langs_mod.ordered(v) for sid, v in out.items()}
    if has_app_context():
        g.series_langs = result
    return result


def series_href(slug, current, season_count):
    return f"/series/{slug}" + (f"?season={current['number']}" if current and season_count > 1 else "")


def series_cards(series_rows, user_id=None):
    """Serien für Poster-Listen: Bild und Ziel der aktuellen Staffel des Nutzers (abgemeldet: Staffel 1)."""
    prog = progress_for(user_id, [s["id"] for s in series_rows])
    lang_map = series_langs()
    cards = []
    for s in series_rows:
        p = prog.get(s["id"])
        cur = p["current"] if p else None
        cards.append({
            **s,
            "cover": (cur["thumbnail_url"] if cur and cur["thumbnail_url"] else s["thumbnail_url"]),
            "season_no": cur["number"] if cur else None,
            "season_id": cur["season_id"] if cur else None,
            "season_count": len(p["seasons"]) if p else 0,
            "rating": cur["avg_rating"] if cur and cur["ratings_count"] else None,
            "href": series_href(s["slug"], cur, len(p["seasons"]) if p else 0),
            "state": p["state"] if p else "NOT_STARTED",
            "langs": lang_map.get(s["id"], []),
            "note": s.get("last_update_note", ""),
        })
    return cards


def next_unwatched_episode(user_id, season_id):
    return db.row(
        "SELECT e.number FROM episodes e LEFT JOIN watch_history h ON h.episode_id = e.id AND h.user_id = ? "
        "AND h.target_type='EPISODE' AND h.completed = 1 "
        "WHERE e.season_id = ? AND e.status='PUBLISHED' AND h.id IS NULL ORDER BY e.number LIMIT 1",
        (user_id, season_id),
    )


# ======================================================================================
# Ranking: Staffeln treten einzeln gegeneinander an
# ======================================================================================

MIN_VOTES = 5          # "Gewicht" des Durchschnitts aller Staffeln: wenige Stimmen werden zum Mittel hin gezogen
TREND_DAYS = 14        # Zeitfenster für "aktuell beliebt"
DEFAULT_MEAN = 7.0     # Startwert, solange noch nichts bewertet wurde


def _season_stats(days=TREND_DAYS):
    cutoff = db.iso_ago(days * 86400)
    rows = db.rows(
        "SELECT se.id AS season_id, se.number, se.title AS season_title, se.thumbnail_url AS season_thumb, "
        "s.id AS series_id, s.title, s.slug, s.thumbnail_url AS series_thumb, "
        "(SELECT COUNT(*) FROM seasons x WHERE x.series_id = s.id AND EXISTS "
        "   (SELECT 1 FROM episodes e WHERE e.season_id = x.id AND e.status='PUBLISHED')) AS season_total, "
        "(SELECT AVG(value) FROM ratings WHERE target_type='SEASON' AND season_id = se.id) AS mean, "
        "(SELECT COUNT(*) FROM ratings WHERE target_type='SEASON' AND season_id = se.id) AS votes, "
        "(SELECT COUNT(*) FROM ratings WHERE target_type='SEASON' AND season_id = se.id AND updated >= ?) AS recent_votes, "
        "(SELECT COUNT(*) FROM watch_history h JOIN episodes e ON e.id = h.episode_id WHERE e.season_id = se.id "
        "   AND h.target_type='EPISODE' AND h.completed = 1 AND h.updated >= ?) AS recent_views "
        "FROM seasons se JOIN series s ON s.id = se.series_id "
        "WHERE s.status='PUBLISHED' AND EXISTS (SELECT 1 FROM episodes e WHERE e.season_id = se.id AND e.status='PUBLISHED')",
        (cutoff, cutoff),
    )
    total_votes = sum(r["votes"] for r in rows)
    global_mean = (sum((r["mean"] or 0) * r["votes"] for r in rows) / total_votes) if total_votes else DEFAULT_MEAN
    for r in rows:
        v = r["votes"]
        r["score"] = (v / (v + MIN_VOTES)) * (r["mean"] or 0) + (MIN_VOTES / (v + MIN_VOTES)) * global_mean
        r["points"] = 3 * r["recent_votes"] + r["recent_views"]
        r["cover"] = r["season_thumb"] or r["series_thumb"]
        r["label"] = r["season_title"] or f"Staffel {r['number']}"
        r["multi"] = r["season_total"] > 1
        r["href"] = f"/series/{r['slug']}" + (f"?season={r['number']}" if r["multi"] else "")
        r["mean_display"] = round(r["mean"], 1) if r["mean"] else None
    return rows


def ranking(kind="alltime", limit=50):
    """kind='alltime': beste Wertung (nach Stimmenzahl gewichtet). kind='trending': Aktivität der letzten Tage."""
    rows = _season_stats()
    if kind == "trending":
        rows = [r for r in rows if r["points"] > 0]
        rows.sort(key=lambda r: (-r["points"], -r["score"], r["title"].lower()))
    else:
        rows = [r for r in rows if r["votes"] > 0]
        rows.sort(key=lambda r: (-r["score"], -r["votes"], r["title"].lower()))
    rows = rows[:limit]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def target_cards(items, user_id=None):
    """Mischliste aus Serien/Filmen (z.B. Watchlist-Einträge) -> einheitliche Karten."""
    series_rows = [it["series"] for it in items if it.get("series")]
    by_id = {c["id"]: c for c in series_cards(series_rows, user_id)}
    out = []
    for it in items:
        if it.get("series"):
            out.append(by_id[it["series"]["id"]])
        elif it.get("movie"):
            m = it["movie"]
            out.append({**m, "cover": m["thumbnail_url"], "href": f"/movies/{m['slug']}", "season_no": None, "season_count": 0,
                        "state": None, "rating": m["avg_rating"] if m["ratings_count"] else None})
    return out


def movie_cards(rows):
    return [{**m, "cover": m["thumbnail_url"], "href": f"/movies/{m['slug']}", "season_no": None, "season_count": 0,
             "state": None, "rating": m["avg_rating"] if m["ratings_count"] else None} for m in rows]
