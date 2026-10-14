"""Verwaltungsbereich /admin und Owner Control Center /owner."""
import os
import platform
import sqlite3
import time
from pathlib import Path

from importlib.metadata import version as pkg_version
from flask import Blueprint, abort, current_app, redirect, render_template, request

from .. import db, linkcheck, services, streamtools
from ..auth import can, current_user, owner_required, role_required

bp = Blueprint("admin_pages", __name__)

ADMIN_NAV = [
    ("/admin", "Übersicht", "ADMIN"),
    ("/admin/series", "Serien", "ADMIN"),
    ("/admin/movies", "Filme", "ADMIN"),
    ("/admin/forum", "Forum", "ADMIN"),
    ("/admin/reports", "Stream-Meldungen", "ADMIN"),
    ("/admin/tickets", "Support-Tickets", "ADMIN"),
    ("/admin/users", "Admins & Nutzer", "HEAD_ADMIN"),
    ("/admin/settings", "Einstellungen", "OWNER"),
]


def _nav():
    from ..auth import has_min_role
    role = current_user()["role"]
    return [{"href": h, "label": label} for h, label, minimum in ADMIN_NAV if has_min_role(role, minimum)]


def _admin(template, **ctx):
    return render_template(template, nav=_nav(), nav_current=request.path, **ctx)


# ======================================================================================
# Admin
# ======================================================================================

@bp.get("/admin")
@role_required(can.manage_content)
def dashboard():
    stats = [
        ("Serien", db.scalar("SELECT COUNT(*) FROM series")),
        ("Filme", db.scalar("SELECT COUNT(*) FROM movies")),
        ("Registrierte Nutzer", db.scalar("SELECT COUNT(*) FROM users")),
        ("Offene Tickets", db.scalar("SELECT COUNT(*) FROM tickets WHERE status='OPEN'")),
        ("Gemeldete Streams", db.scalar("SELECT COUNT(*) FROM stream_reports WHERE status='OPEN'")),
        ("Tote Links", db.scalar("SELECT COUNT(*) FROM stream_checks WHERE status='DEAD'")),
    ]
    return _admin("admin/dashboard.html", stats=stats)


# ---- Serien ----------------------------------------------------------------------------

@bp.get("/admin/series")
@role_required(can.manage_content)
def series_list():
    items = db.rows("SELECT * FROM series ORDER BY created DESC")
    for s in items:
        s["season_count"] = db.scalar("SELECT COUNT(*) FROM seasons WHERE series_id=?", (s["id"],))
        s["episode_count"] = db.scalar(
            "SELECT COUNT(*) FROM episodes e JOIN seasons se ON se.id=e.season_id WHERE se.series_id=?", (s["id"],))
    return _admin("admin/series_list.html", items=items)


def _series_editor_data(series_id=None):
    if not series_id:
        return {"id": None, "title": "", "description": "", "thumbnailUrl": "", "bannerUrl": "", "status": "DRAFT",
                "genres": [], "tags": [], "altTitles": [], "year": "", "airStatus": "", "seasons": []}
    full = services.load_full_series(series_id)
    if not full:
        abort(404)
    return {
        "id": full["id"], "title": full["title"], "description": full["description"],
        "thumbnailUrl": full["thumbnail_url"], "bannerUrl": full["banner_url"], "status": full["status"],
        "genres": full["genres"], "tags": full["tags"], "altTitles": full["alt_titles"] or [],
        "year": full["year"] or "", "airStatus": full["air_status"] or "",
        "seasons": [{
            "id": s["id"], "number": s["number"], "title": s["title"], "thumbnailUrl": s["thumbnail_url"],
            "episodes": [{"id": e["id"], "number": e["number"], "title": e["title"], "airedAt": e["aired_at"],
                          "streams": e["streams"]}
                         for e in s["episodes"]],
        } for s in full["seasons"]],
    }


@bp.get("/admin/series/new")
@role_required(can.manage_content)
def series_new():
    return _admin("admin/series_edit.html", data=_series_editor_data(), heading="Neue Serie")


@bp.get("/admin/series/<series_id>/edit")
@role_required(can.manage_content)
def series_edit(series_id):
    return _admin("admin/series_edit.html", data=_series_editor_data(series_id), heading="Serie bearbeiten")


# ---- Filme -----------------------------------------------------------------------------

@bp.get("/admin/movies")
@role_required(can.manage_content)
def movies_list():
    return _admin("admin/movies_list.html", items=db.rows("SELECT * FROM movies ORDER BY created DESC"))


def _movie_editor_data(movie_id=None):
    if not movie_id:
        return {"id": None, "title": "", "description": "", "thumbnailUrl": "", "bannerUrl": "", "status": "DRAFT",
                "genres": [], "tags": [], "altTitles": [], "year": "", "streams": [{"label": "", "url": "", "lang": "GERSUB"}]}
    m = db.get("movies", movie_id)
    if not m:
        abort(404)
    return {
        "id": m["id"], "title": m["title"], "description": m["description"], "thumbnailUrl": m["thumbnail_url"],
        "bannerUrl": m["banner_url"], "status": m["status"],
        "genres": services.taxonomy_names("genres", m["genre_ids"]), "tags": services.taxonomy_names("tags", m["tag_ids"]),
        "altTitles": m["alt_titles"] or [], "year": m["year"] or "",
        "streams": m["streams"] or [{"label": "", "url": "", "lang": "GERSUB"}],
    }


@bp.get("/admin/movies/new")
@role_required(can.manage_content)
def movie_new():
    return _admin("admin/movie_edit.html", data=_movie_editor_data(), heading="Neuer Film")


@bp.get("/admin/movies/<movie_id>/edit")
@role_required(can.manage_content)
def movie_edit(movie_id):
    return _admin("admin/movie_edit.html", data=_movie_editor_data(movie_id), heading="Film bearbeiten")


# ---- Forum, Tickets, Nutzer, Einstellungen ---------------------------------------------

@bp.get("/admin/forum")
@role_required(can.moderate)
def forum():
    cats = db.rows('SELECT * FROM forum_categories ORDER BY "order", name')
    threads = services.enrich_users(db.rows(
        "SELECT t.*, c.name AS category_name, c.slug AS category_slug FROM forum_threads t "
        "JOIN forum_categories c ON c.id=t.category_id ORDER BY t.created DESC LIMIT 200"), "user_id")
    return _admin("admin/forum.html", categories=cats, threads=threads)


@bp.get("/admin/tickets")
@role_required(can.moderate)
def tickets():
    services.cleanup_closed_tickets()
    items = services.enrich_users(db.rows("SELECT * FROM tickets ORDER BY updated DESC LIMIT 200"), "user_id")
    labels = {"OPEN": "Offen", "IN_PROGRESS": "In Bearbeitung", "RESOLVED": "Gelöst", "CLOSED": "Geschlossen"}
    return _admin("admin/tickets.html", items=items, labels=labels)


@bp.get("/admin/tickets/<ticket_id>")
@role_required(can.moderate)
def ticket(ticket_id):
    return redirect(f"/support/{ticket_id}")


@bp.get("/admin/users")
@role_required(can.manage_admins, redirect_to="admin_pages.dashboard")
def users():
    actor = current_user()
    items = db.rows("SELECT id, username, email, role, is_banned, created FROM users ORDER BY created DESC")
    return _admin("admin/users.html", items=items, actor=actor)


@bp.get("/admin/settings")
@role_required(can.manage_settings, redirect_to="admin_pages.dashboard")
def settings():
    return _admin("admin/settings.html", settings=db.all_settings())


# ======================================================================================
# Owner Control Center
# ======================================================================================

OWNER_NAV = [
    ("/owner", "Übersicht"), ("/owner/database", "Datenbank"), ("/owner/audit", "Audit-Log"),
    ("/owner/settings", "System & Einstellungen"), ("/admin", "Admin-Bereich"),
]
DB_TABLES = [
    "users", "series", "seasons", "episodes", "movies", "genres", "tags", "ratings", "watch_history",
    "watchlist_items", "subscriptions", "notifications", "user_collections", "collection_items", "forum_categories",
    "forum_threads", "forum_posts", "tickets", "ticket_messages", "profile_favorites", "audit_logs", "app_settings",
]
REDACTED = {"password_hash", "totp_secret", "totp_recovery_codes", "token_hash"}


def _owner(template, **ctx):
    return render_template(template, owner_nav=OWNER_NAV, nav_current=request.path, **ctx)


@bp.get("/owner")
@owner_required
def owner_home():
    cards = [(label, db.scalar(f'SELECT COUNT(*) FROM "{table}"')) for label, table in (
        ("Benutzer", "users"), ("Serien", "series"), ("Filme", "movies"), ("Episoden", "episodes"),
        ("Audit-Ereignisse", "audit_logs"), ("Aktive Sessions", "sessions"))]
    return _owner("owner/home.html", cards=cards)


@bp.get("/owner/database")
@owner_required
def owner_database():
    selected = request.args.get("table")
    if selected not in DB_TABLES:
        selected = None
    counts = [(t, db.scalar(f'SELECT COUNT(*) FROM "{t}"')) for t in DB_TABLES]
    columns, data = [], []
    if selected:
        info = db.get_db().execute(f'PRAGMA table_info("{selected}")').fetchall()
        columns = [c["name"] for c in info if c["name"] not in REDACTED]
        order = "updated" if selected == "app_settings" else ("created" if any(c["name"] == "created" for c in info) else "rowid")
        quoted = ", ".join(f'"{c}"' for c in columns)
        data = db.get_db().execute(f'SELECT {quoted} FROM "{selected}" ORDER BY "{order}" DESC LIMIT 100').fetchall()
    return _owner("owner/database.html", counts=counts, selected=selected, columns=columns, data=data)


@bp.get("/owner/audit")
@owner_required
def owner_audit():
    items = db.rows(
        "SELECT a.*, u.username AS actor_username FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id "
        "ORDER BY a.created DESC LIMIT 100")
    return _owner("owner/audit.html", items=items)


def _dir_size(path: str) -> int:
    total = 0
    p = Path(path)
    if p.is_dir():
        for f in p.iterdir():
            if f.is_file():
                total += f.stat().st_size
    return total


@bp.get("/owner/settings")
@owner_required
def owner_settings():
    started = time.perf_counter()
    db.scalar("SELECT 1")
    latency = round((time.perf_counter() - started) * 1000, 2)
    db_path = current_app.config["DB_PATH"]
    info = {
        "latency": latency,
        "sqlite": sqlite3.sqlite_version,
        "python": platform.python_version(),
        "flask": pkg_version("flask"),
        "db_size": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
        "upload_size": _dir_size(current_app.config["STORAGE_DIR"]),
        "owner_identity": ", ".join(current_app.config["OWNER_EMAILS"] + current_app.config["OWNER_USERNAMES"]) or "nicht konfiguriert",
    }
    return _owner("owner/settings.html", settings=db.all_settings(), info=info)


# ---- Stream-Meldungen & Link-Check ------------------------------------------------------------

@bp.get("/admin/reports")
@role_required(can.moderate)
def reports():
    status = request.args.get("status", "OPEN")
    if status not in ("OPEN", "FIXED", "IGNORED"):
        status = "OPEN"
    rows = db.rows("SELECT * FROM stream_reports WHERE status=? ORDER BY count DESC, updated DESC LIMIT 200", (status,))
    checks = {r["url"]: r for r in db.rows("SELECT * FROM stream_checks")}
    items = []
    for r in rows:
        info = streamtools.describe_target(r["target_type"], r["target_id"])
        if not info:
            continue
        items.append({**r, **info, "check": checks.get(r["url"])})
    dead = []
    for c in db.rows("SELECT * FROM stream_checks WHERE status='DEAD' ORDER BY checked_at DESC LIMIT 200"):
        dead.append(c)
    state = linkcheck.get_state(db.get_db())
    return _admin("admin/reports.html", items=items, status=status, dead=dead, state=state,
                  open_count=db.scalar("SELECT COUNT(*) FROM stream_reports WHERE status='OPEN'"))
