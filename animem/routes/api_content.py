"""/api/series, /api/movies, /api/ratings, /api/uploads, /api/media, /api/watch, /api/health."""
import os
import sqlite3
from pathlib import Path

from flask import Blueprint, current_app, request, send_file

from .. import auth, db, notify, security, services, streamtools, validation
from ..auth import can, current_user, login_required, role_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_content", __name__)


def _json():
    return request.get_json(silent=True)


def _page_args(default_limit=24, max_limit=50):
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(max_limit, max(1, int(request.args.get("limit", default_limit))))
    except ValueError:
        page, limit = 1, default_limit
    return page, limit


def _limit(scope, limit, window):
    user = current_user()
    return security.rate_limit(scope, limit, window, key=user["id"] if user else None)


# ======================================================================================
# Serien
# ======================================================================================

@bp.get("/api/series")
def list_series():
    wants_admin = request.args.get("admin") == "1"
    if wants_admin:
        user = current_user()
        if not user or not can.manage_content(user["role"]):
            return fail("Nicht berechtigt", 403)
    page, limit = _page_args()
    where = "" if wants_admin else "WHERE status='PUBLISHED'"
    items = db.rows(f"SELECT * FROM series {where} ORDER BY avg_rating DESC, created DESC LIMIT ? OFFSET ?", (limit, (page - 1) * limit))
    return ok(items)


def _delete_series_dependents(series_id):
    episode_ids = [r["id"] for r in db.rows(
        "SELECT e.id FROM episodes e JOIN seasons s ON s.id=e.season_id WHERE s.series_id=?", (series_id,))]
    for eid in episode_ids:
        db.run("DELETE FROM ratings WHERE episode_id=?", (eid,))
        db.run("DELETE FROM watch_history WHERE episode_id=?", (eid,))
        db.run("DELETE FROM stream_reports WHERE target_type='EPISODE' AND target_id=?", (eid,))
    db.run("DELETE FROM ratings WHERE series_id=?", (series_id,))
    db.run("DELETE FROM ratings WHERE season_id IN (SELECT id FROM seasons WHERE series_id=?)", (series_id,))
    db.run("DELETE FROM profile_favorites WHERE series_id=?", (series_id,))


def _episode_fields(ep):
    first = ep["streams"][0] if ep["streams"] else None
    return {
        "number": ep["number"], "title": ep["title"], "streams": ep["streams"], "aired_at": ep["aired_at"],
        "embed_url": first["url"] if first else "", "embed_provider": first["label"] if first else "",
        "status": "PUBLISHED" if first else "DRAFT",  # ohne Stream: nur angekündigt (Kalender), nicht abrufbar
    }


def _series_extra(v):
    return {"alt_titles": v["alt_titles"], "year": v["year"], "air_status": v["air_status"]}


@bp.post("/api/series")
@role_required(can.manage_content)
def create_series():
    allowed, retry = _limit("series-create", 20, 60)
    if not allowed:
        return limited_response(retry)
    try:
        v = validation.series(_json())
    except validation.ValidationError as exc:
        return fail(str(exc))
    user = current_user()
    try:
        with db.transaction():
            series = db.insert("series", {
                "title": v["title"], "slug": services.unique_slug("series", v["title"]), "description": v["description"],
                "thumbnail_url": v["thumbnail_url"], "banner_url": v["banner_url"], "status": v["status"],
                "created_by": user["id"], "content_updated": db.utcnow(), **_series_extra(v),
                "genre_ids": services.resolve_taxonomy_ids("genres", v["genres"]),
                "tag_ids": services.resolve_taxonomy_ids("tags", v["tags"]),
            })
            for s in v["seasons"]:
                season = db.insert("seasons", {"series_id": series["id"], "number": s["number"], "title": s["title"],
                                               "thumbnail_url": s["thumbnail_url"]})
                for ep in s["episodes"]:
                    db.insert("episodes", {"season_id": season["id"], **_episode_fields(ep)})
    except sqlite3.IntegrityError:
        return fail("Staffel- oder Folgennummern dürfen sich nicht doppeln.")
    return ok(services.load_full_series(series["id"]), 201)


@bp.get("/api/series/<series_id>")
@role_required(can.manage_content)
def get_series(series_id):
    full = services.load_full_series(series_id)
    return ok(full) if full else fail("Serie nicht gefunden", 404)


@bp.patch("/api/series/<series_id>")
@role_required(can.manage_content)
def update_series(series_id):
    allowed, retry = _limit("series-update", 30, 60)
    if not allowed:
        return limited_response(retry)
    try:
        v = validation.series(_json())
    except validation.ValidationError as exc:
        return fail(str(exc))
    if not db.get("series", series_id):
        return fail("Serie nicht gefunden", 404)

    before = notify.snapshot(series_id)
    try:
        with db.transaction():
            db.update("series", series_id, {
                "title": v["title"], "slug": services.unique_slug("series", v["title"], series_id),
                "description": v["description"], "thumbnail_url": v["thumbnail_url"], "banner_url": v["banner_url"],
                "status": v["status"], **_series_extra(v),
                "genre_ids": services.resolve_taxonomy_ids("genres", v["genres"]),
                "tag_ids": services.resolve_taxonomy_ids("tags", v["tags"]),
            })
            existing_seasons = {s["id"]: s for s in db.rows("SELECT * FROM seasons WHERE series_id=?", (series_id,))}
            # Nummern kurz negieren, damit Umnummerieren/Tauschen keine UNIQUE-Konflikte erzeugt.
            db.run("UPDATE seasons SET number = -number WHERE series_id=?", (series_id,))
            keep_seasons = set()
            for s in v["seasons"]:
                if s["id"]:
                    if s["id"] not in existing_seasons:
                        raise PermissionError("Eine Staffel gehört nicht zu dieser Serie.")
                    db.update("seasons", s["id"], {"number": s["number"], "title": s["title"], "thumbnail_url": s["thumbnail_url"]})
                    season_id = s["id"]
                else:
                    season_id = db.insert("seasons", {"series_id": series_id, "number": s["number"], "title": s["title"],
                                                      "thumbnail_url": s["thumbnail_url"]})["id"]
                keep_seasons.add(season_id)

                existing_eps = {e["id"]: e for e in db.rows("SELECT * FROM episodes WHERE season_id=?", (season_id,))}
                db.run("UPDATE episodes SET number = -number WHERE season_id=?", (season_id,))
                keep_eps = set()
                for ep in s["episodes"]:
                    if ep["id"]:
                        if ep["id"] not in existing_eps:
                            raise PermissionError("Eine Episode gehört nicht zu dieser Staffel.")
                        db.update("episodes", ep["id"], _episode_fields(ep))
                        keep_eps.add(ep["id"])
                    else:
                        keep_eps.add(db.insert("episodes", {"season_id": season_id, **_episode_fields(ep)})["id"])
                for eid in set(existing_eps) - keep_eps:
                    db.run("DELETE FROM stream_reports WHERE target_type='EPISODE' AND target_id=?", (eid,))
                    db.run("DELETE FROM ratings WHERE episode_id=?", (eid,))
                    db.run("DELETE FROM watch_history WHERE episode_id=?", (eid,))
                    db.delete("episodes", eid)
            for sid in set(existing_seasons) - keep_seasons:
                for e in db.rows("SELECT id FROM episodes WHERE season_id=?", (sid,)):
                    db.run("DELETE FROM ratings WHERE episode_id=?", (e["id"],))
                    db.run("DELETE FROM watch_history WHERE episode_id=?", (e["id"],))
                db.run("DELETE FROM ratings WHERE season_id=?", (sid,))
                db.delete("seasons", sid)
            services.recalc_series_rating(series_id)
    except PermissionError as exc:
        return fail(str(exc))
    except sqlite3.IntegrityError:
        return fail("Staffel- oder Folgennummern dürfen sich nicht doppeln.")
    for r in db.rows("SELECT e.id, e.streams FROM episodes e JOIN seasons se ON se.id=e.season_id WHERE se.series_id=?", (series_id,)):
        streamtools.close_stale_reports("EPISODE", r["id"], {s["url"] for s in r["streams"] or []})
    notify.notify_changes(series_id, before, notify.snapshot(series_id))  # Abonnenten informieren (nach Sprachfilter)
    return ok(services.load_full_series(series_id))


@bp.delete("/api/series/<series_id>")
@role_required(can.manage_admins)
def delete_series(series_id):
    if not db.get("series", series_id):
        return fail("Serie nicht gefunden", 404)
    with db.transaction():
        _delete_series_dependents(series_id)
        db.delete("series", series_id)
    return ok()


# ======================================================================================
# Filme
# ======================================================================================

@bp.get("/api/movies")
def list_movies():
    wants_admin = request.args.get("admin") == "1"
    if wants_admin:
        user = current_user()
        if not user or not can.manage_content(user["role"]):
            return fail("Nicht berechtigt", 403)
    page, limit = _page_args()
    where = "" if wants_admin else "WHERE status='PUBLISHED'"
    return ok(db.rows(f"SELECT * FROM movies {where} ORDER BY created DESC LIMIT ? OFFSET ?", (limit, (page - 1) * limit)))


@bp.post("/api/movies")
@role_required(can.manage_content)
def create_movie():
    allowed, retry = _limit("movie-create", 30, 60)
    if not allowed:
        return limited_response(retry)
    try:
        v = validation.movie(_json())
    except validation.ValidationError as exc:
        return fail(str(exc))
    with db.transaction():
        movie = db.insert("movies", {
            "title": v["title"], "slug": services.unique_slug("movies", v["title"]), "description": v["description"],
            "thumbnail_url": v["thumbnail_url"], "banner_url": v["banner_url"], "streams": v["streams"],
            "embed_url": v["streams"][0]["url"], "embed_provider": v["streams"][0]["label"], "status": v["status"],
            "created_by": current_user()["id"], "alt_titles": v["alt_titles"], "year": v["year"],
            "genre_ids": services.resolve_taxonomy_ids("genres", v["genres"]),
            "tag_ids": services.resolve_taxonomy_ids("tags", v["tags"]),
        })
    return ok(movie, 201)


@bp.get("/api/movies/<movie_id>")
@role_required(can.manage_content)
def get_movie(movie_id):
    movie = db.get("movies", movie_id)
    if not movie:
        return fail("Film nicht gefunden", 404)
    return ok({**movie, "genres": services.taxonomy_names("genres", movie["genre_ids"]),
               "tags": services.taxonomy_names("tags", movie["tag_ids"])})


@bp.patch("/api/movies/<movie_id>")
@role_required(can.manage_content)
def update_movie(movie_id):
    allowed, retry = _limit("movie-update", 60, 60)
    if not allowed:
        return limited_response(retry)
    try:
        v = validation.movie(_json(), partial=True)
    except validation.ValidationError as exc:
        return fail(str(exc))
    if not db.get("movies", movie_id):
        return fail("Film nicht gefunden", 404)
    data = {k: v[k] for k in ("title", "description", "thumbnail_url", "banner_url", "status", "alt_titles", "year") if k in v}
    with db.transaction():
        if "title" in v:
            data["slug"] = services.unique_slug("movies", v["title"], movie_id)
        if "streams" in v:
            data.update(streams=v["streams"], embed_url=v["streams"][0]["url"], embed_provider=v["streams"][0]["label"])
        if "genres" in v:
            data["genre_ids"] = services.resolve_taxonomy_ids("genres", v["genres"])
        if "tags" in v:
            data["tag_ids"] = services.resolve_taxonomy_ids("tags", v["tags"])
        movie = db.update("movies", movie_id, data)
    streamtools.close_stale_reports("MOVIE", movie_id, {s["url"] for s in movie["streams"] or []})
    return ok(movie)


@bp.delete("/api/movies/<movie_id>")
@role_required(can.manage_admins)
def delete_movie(movie_id):
    if not db.get("movies", movie_id):
        return fail("Film nicht gefunden", 404)
    with db.transaction():
        db.run("DELETE FROM ratings WHERE movie_id=?", (movie_id,))
        db.run("DELETE FROM stream_reports WHERE target_type='MOVIE' AND target_id=?", (movie_id,))
        db.run("DELETE FROM watch_history WHERE movie_id=?", (movie_id,))
        db.run("DELETE FROM profile_favorites WHERE movie_id=?", (movie_id,))
        db.delete("movies", movie_id)
    return ok()


# ======================================================================================
# Bewertungen
# ======================================================================================

TARGET_FIELDS = {"SEASON": "season_id", "MOVIE": "movie_id", "EPISODE": "episode_id"}
TARGET_TABLES = {"SEASON": "seasons", "MOVIE": "movies", "EPISODE": "episodes"}


@bp.get("/api/ratings")
def list_ratings():
    target_type, target_id = request.args.get("targetType"), request.args.get("targetId")
    if target_type not in TARGET_FIELDS or not target_id:
        return fail("targetType und targetId sind erforderlich.")
    field = TARGET_FIELDS[target_type]
    raw = db.rows(
        f"SELECT * FROM ratings WHERE target_type=? AND {field}=? AND comment <> '' ORDER BY created DESC LIMIT 200",
        (target_type, target_id),
    )
    out = []
    for r in services.enrich_users(raw, "user_id"):
        u = r["user"] or {}
        out.append({
            "id": r["id"], "value": r["value"], "comment": r["comment"], "createdAt": r["created"],
            "username": u.get("username"), "displayName": u.get("display_name") or None,
            "avatarUrl": u.get("avatar_url") or None,
        })
    return ok(out)


@bp.post("/api/ratings")
@login_required
def save_rating():
    user = current_user()
    allowed, retry = _limit("rating", 30, 60)
    if not allowed:
        return limited_response(retry)
    try:
        v = validation.rating(_json())
    except validation.ValidationError:
        return fail("Ungültige Bewertung.")
    field, table = TARGET_FIELDS[v["target_type"]], TARGET_TABLES[v["target_type"]]
    target = db.get(table, v["target_id"])
    if not target:
        return fail("Bewertungsziel nicht gefunden.", 404)
    if v["target_type"] == "SEASON":
        parent = db.get("series", target["series_id"])
        if not parent or parent["status"] != "PUBLISHED":
            return fail("Diese Serie ist noch nicht veröffentlicht.", 403)
    elif target.get("status") and target["status"] != "PUBLISHED":
        return fail("Dieses Ziel ist noch nicht veröffentlicht.", 403)

    with db.transaction():
        existing = db.row(
            f"SELECT * FROM ratings WHERE user_id=? AND target_type=? AND {field}=?",
            (user["id"], v["target_type"], v["target_id"]),
        )
        if existing:
            rating = db.update("ratings", existing["id"], {"value": v["value"], "comment": v["comment"]})
        else:
            rating = db.insert("ratings", {
                "user_id": user["id"], "target_type": v["target_type"], field: v["target_id"],
                "value": v["value"], "comment": v["comment"],
            })
        summary = {}
        if v["target_type"] == "SEASON":
            services.recalc_season_rating(v["target_id"])
            fresh = db.get("seasons", v["target_id"])
            summary = {"avg": fresh["avg_rating"], "count": fresh["ratings_count"]}
        elif v["target_type"] == "MOVIE":
            services.recalc_rating("MOVIE", v["target_id"])
            fresh = db.get("movies", v["target_id"])
            summary = {"avg": fresh["avg_rating"], "count": fresh["ratings_count"]}
    return ok({**rating, **summary})


# ======================================================================================
# Uploads & Medien
# ======================================================================================

MAX_UPLOAD = 10 * 1024 * 1024
MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
EXT_MIME = {v: k for k, v in MIME_EXT.items()}


def _magic_ok(mime: str, head: bytes) -> bool:
    if mime == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if mime == "image/gif":
        return head.startswith(b"GIF8")
    if mime == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


@bp.post("/api/uploads")
@login_required
def upload():
    allowed, retry = _limit("upload", 20, 3600)
    if not allowed:
        return limited_response(retry)
    file = request.files.get("file")
    if file is None:
        return fail("Keine Datei übergeben.")
    data = file.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        return fail("Datei muss zwischen 1 Byte und 10 MB groß sein.", 413)
    mime = (file.mimetype or "").lower()
    if mime not in MIME_EXT:
        return fail("Nur PNG, JPEG, WebP und GIF sind erlaubt.", 415)
    if not _magic_ok(mime, data[:16]):
        return fail("Dateiinhalt und Dateityp stimmen nicht überein.", 415)

    storage = Path(current_app.config["STORAGE_DIR"])
    storage.mkdir(parents=True, exist_ok=True)
    file_id = db.new_id()
    filename = f"{file_id}{MIME_EXT[mime]}"  # Endung kommt vom geprüften Typ, nie vom Dateinamen
    (storage / filename).write_bytes(data)
    record = db.insert("uploads", {"id": file_id, "file": filename, "mime": mime, "size": len(data)})
    return ok({"url": f"/api/media/{record['id']}", "id": record["id"]}, 201)


@bp.get("/api/media/<media_id>")
def media(media_id):
    record = db.get("uploads", media_id)
    if not record:
        return fail("Datei nicht gefunden", 404)
    name = record["file"]
    path = Path(current_app.config["STORAGE_DIR"]) / os.path.basename(name)
    if name != os.path.basename(name) or not path.is_file():
        return fail("Datei nicht gefunden", 404)
    mime = EXT_MIME.get(path.suffix.lower(), "application/octet-stream")
    resp = send_file(path, mimetype=mime, max_age=31536000, conditional=True)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return resp


# ======================================================================================
# Fortschritt & Health
# ======================================================================================

@bp.post("/api/watch/progress")
@login_required
def watch_progress():
    user = current_user()
    allowed, retry = _limit("watch-progress", 60, 60)
    if not allowed:
        return limited_response(retry)
    data = _json()
    if not isinstance(data, dict):
        return fail("Ungültige Anfrage.")
    target_type = data.get("targetType")
    episode_id, movie_id = data.get("episodeId"), data.get("movieId")
    if target_type == "EPISODE" and episode_id and not movie_id:
        field, target_id, table = "episode_id", episode_id, "episodes"
    elif target_type == "MOVIE" and movie_id and not episode_id:
        field, target_id, table = "movie_id", movie_id, "movies"
    else:
        return fail("Ungültige Anfrage.")
    if not isinstance(target_id, str) or not db.get(table, target_id):
        return fail("Ziel nicht gefunden.", 404)
    with db.transaction():
        existing = db.row(
            f"SELECT * FROM watch_history WHERE user_id=? AND target_type=? AND {field}=?",
            (user["id"], target_type, target_id),
        )
        if existing and existing["completed"]:
            return ok(existing)  # schon gesehen
        # Seit dem Öffnen der Seite müssen (fast) 3 Minuten vergangen sein – sonst ließe sich der Status per API fälschen.
        opened = existing["updated"] if existing else None
        if not opened or opened > db.iso_ago(services.WATCH_SECONDS - services.WATCH_TOLERANCE):
            return fail("Noch nicht lange genug angesehen.", 425)
        rec = db.update("watch_history", existing["id"], {"completed": True, "progress_sec": services.WATCH_SECONDS})
    return ok(rec)


@bp.get("/api/health")
def health():
    try:
        db.scalar("SELECT 1")
        return ok({"status": "ok", "database": "ok"})
    except Exception:
        return fail("degraded", 503)
