"""Gemeinsame Geschäftslogik: Slugs, Genres/Tags, Anreicherung, Bewertungen, Audit, Tickets."""
import re
import unicodedata

from flask import request

from . import db
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
