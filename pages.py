"""Öffentliche HTML-Seiten."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from .. import db, services
from ..auth import can, current_user

bp = Blueprint("pages", __name__)


def _published_series():
    return db.rows("SELECT * FROM series WHERE status='PUBLISHED' ORDER BY title COLLATE NOCASE")


def _published_movies():
    return db.rows("SELECT * FROM movies WHERE status='PUBLISHED' ORDER BY title COLLATE NOCASE")


def _login_redirect():
    return redirect(url_for("auth_pages.login", next=request.path))


def _track_history(user, target_type, field, target_id):
    """Verlauf protokollieren (find-or-create); 'gesehen' setzt erst /api/watch/progress nach 2 Minuten."""
    existing = db.row(
        f"SELECT id FROM watch_history WHERE user_id=? AND target_type=? AND {field}=?", (user["id"], target_type, target_id)
    )
    if existing:
        db.update("watch_history", existing["id"], {})
    else:
        db.insert("watch_history", {"user_id": user["id"], "target_type": target_type, field: target_id,
                                    "progress_sec": 0, "completed": False})


def _streams(record):
    streams = record.get("streams") or []
    if streams:
        return [{"label": s.get("label", ""), "url": s.get("url", "")} for s in streams]
    if record.get("embed_url"):
        return [{"label": record.get("embed_provider", ""), "url": record["embed_url"]}]
    return []


# ---- Start, Listen, Suche --------------------------------------------------------------

@bp.get("/")
def home():
    top = db.rows("SELECT * FROM series WHERE status='PUBLISHED' ORDER BY avg_rating DESC, created DESC LIMIT 3")
    latest = db.rows("SELECT * FROM series WHERE status='PUBLISHED' ORDER BY created DESC LIMIT 12")
    return render_template("home.html", top=top if len(top) == 3 else [], latest=latest)


@bp.get("/series")
def series_list():
    return render_template("series_list.html", items=_published_series())


@bp.get("/movies")
def movies_list():
    return render_template("movies_list.html", items=_published_movies())


@bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    needle = q.lower()
    series = [s for s in _published_series() if not needle or needle in s["title"].lower()][:24]
    movies = [m for m in _published_movies() if not needle or needle in m["title"].lower()][:24]
    return render_template("search.html", q=q, series=series, movies=movies)


@bp.get("/categories")
def categories():
    return render_template("categories.html", genres=db.rows("SELECT * FROM genres ORDER BY name COLLATE NOCASE"))


def _taxonomy_page(table, slug, template):
    item = db.row(f'SELECT * FROM "{table}" WHERE slug=?', (slug,))
    if not item:
        abort(404)
    field = "genre_ids" if table == "genres" else "tag_ids"
    return render_template(
        template, item=item,
        series=services.find_by_taxonomy("series", field, item["id"]),
        movies=services.find_by_taxonomy("movies", field, item["id"]),
    )


@bp.get("/genres/<slug>")
def genre(slug):
    return _taxonomy_page("genres", slug, "taxonomy.html")


@bp.get("/tags/<slug>")
def tag(slug):
    return _taxonomy_page("tags", slug, "taxonomy.html")


# ---- Serien & Filme --------------------------------------------------------------------

@bp.get("/series/<slug>")
def series_detail(slug):
    user = current_user()
    series = db.row("SELECT * FROM series WHERE slug=? AND status='PUBLISHED'", (slug,))
    if not series:
        abort(404)
    seasons = db.rows("SELECT * FROM seasons WHERE series_id=? ORDER BY number", (series["id"],))
    episode_ids = []
    for s in seasons:
        s["episodes"] = db.rows("SELECT * FROM episodes WHERE season_id=? AND status='PUBLISHED' ORDER BY number", (s["id"],))
        episode_ids += [e["id"] for e in s["episodes"]]
    tags = services.taxonomy_items("tags", series["tag_ids"])
    genres = services.taxonomy_items("genres", series["genre_ids"])

    state = {"rating": None, "comment": "", "subscribed": False, "watchlist": False, "collections": [], "watched": set()}
    if user:
        rating = db.row("SELECT value, comment FROM ratings WHERE user_id=? AND target_type='SERIES' AND series_id=?", (user["id"], series["id"]))
        if rating:
            state["rating"], state["comment"] = rating["value"], rating["comment"]
        state["subscribed"] = bool(db.row("SELECT 1 AS x FROM subscriptions WHERE user_id=? AND series_id=?", (user["id"], series["id"])))
        state["watchlist"] = bool(db.row("SELECT 1 AS x FROM watchlist_items WHERE user_id=? AND series_id=?", (user["id"], series["id"])))
        state["collections"] = _collections_for(user, "series_id", series["id"])
        if episode_ids:
            marks = ",".join("?" for _ in episode_ids)
            state["watched"] = {r["episode_id"] for r in db.rows(
                f"SELECT episode_id FROM watch_history WHERE user_id=? AND target_type='EPISODE' AND completed=1 AND episode_id IN ({marks})",
                [user["id"]] + episode_ids)}
    return render_template("series_detail.html", series=series, seasons=seasons, tags=tags, genres=genres, **state)


def _collections_for(user, field, target_id):
    cols = db.rows("SELECT id, title FROM user_collections WHERE user_id=? ORDER BY created DESC", (user["id"],))
    member = {r["collection_id"] for r in db.rows(
        f"SELECT ci.collection_id FROM collection_items ci JOIN user_collections uc ON uc.id=ci.collection_id "
        f"WHERE uc.user_id=? AND ci.{field}=?", (user["id"], target_id))}
    return [{**c, "member": c["id"] in member} for c in cols]


@bp.get("/series/<slug>/s/<int:season_no>/e/<int:episode_no>")
def episode(slug, season_no, episode_no):
    user = current_user()
    series = db.row("SELECT * FROM series WHERE slug=? AND status='PUBLISHED'", (slug,))
    if not series:
        abort(404)
    season = db.row("SELECT * FROM seasons WHERE series_id=? AND number=?", (series["id"], season_no))
    if not season:
        abort(404)
    ep = db.row("SELECT * FROM episodes WHERE season_id=? AND number=? AND status='PUBLISHED'", (season["id"], episode_no))
    if not ep:
        abort(404)

    my_rating, my_comment = None, ""
    if user:
        r = db.row("SELECT value, comment FROM ratings WHERE user_id=? AND target_type='EPISODE' AND episode_id=?", (user["id"], ep["id"]))
        if r:
            my_rating, my_comment = r["value"], r["comment"]
        _track_history(user, "EPISODE", "episode_id", ep["id"])

    next_ep = db.row("SELECT number FROM episodes WHERE season_id=? AND status='PUBLISHED' AND number>? ORDER BY number LIMIT 1", (season["id"], ep["number"]))
    next_url = None
    if next_ep:
        next_url = url_for("pages.episode", slug=slug, season_no=season_no, episode_no=next_ep["number"])
    else:
        nxt = db.row(
            "SELECT s.number AS sn, e.number AS en FROM seasons s JOIN episodes e ON e.season_id=s.id "
            "WHERE s.series_id=? AND s.number>? AND e.status='PUBLISHED' ORDER BY s.number, e.number LIMIT 1",
            (series["id"], season["number"]))
        if nxt:
            next_url = url_for("pages.episode", slug=slug, season_no=nxt["sn"], episode_no=nxt["en"])
    return render_template("episode.html", series=series, season=season, ep=ep, streams=_streams(ep),
                           my_rating=my_rating, my_comment=my_comment, next_url=next_url)


@bp.get("/movies/<slug>")
def movie_detail(slug):
    user = current_user()
    movie = db.row("SELECT * FROM movies WHERE slug=? AND status='PUBLISHED'", (slug,))
    if not movie:
        abort(404)
    state = {"rating": None, "comment": "", "watchlist": False, "collections": []}
    if user:
        r = db.row("SELECT value, comment FROM ratings WHERE user_id=? AND target_type='MOVIE' AND movie_id=?", (user["id"], movie["id"]))
        if r:
            state["rating"], state["comment"] = r["value"], r["comment"]
        state["watchlist"] = bool(db.row("SELECT 1 AS x FROM watchlist_items WHERE user_id=? AND movie_id=?", (user["id"], movie["id"])))
        state["collections"] = _collections_for(user, "movie_id", movie["id"])
        _track_history(user, "MOVIE", "movie_id", movie["id"])
    return render_template("movie_detail.html", movie=movie, streams=_streams(movie),
                           tags=services.taxonomy_items("tags", movie["tag_ids"]),
                           genres=services.taxonomy_items("genres", movie["genre_ids"]), **state)


# ---- Bibliothek ------------------------------------------------------------------------

LIBRARY_TABS = [
    ("watchlist", "Watchlist"), ("subscriptions", "Abonniert"), ("history", "Verlauf"),
    ("watched-episodes", "Gesehene Folgen"), ("watched-movies", "Gesehene Filme"), ("collections", "Sammlungen"),
]


@bp.get("/library")
def library():
    user = current_user()
    if not user:
        return _login_redirect()
    tab = request.args.get("tab", "watchlist")
    if tab not in dict(LIBRARY_TABS):
        tab = "watchlist"
    uid = user["id"]
    data = {}
    if tab == "watchlist":
        data["items"] = services.enrich_targets(db.rows("SELECT * FROM watchlist_items WHERE user_id=? ORDER BY created DESC", (uid,)))
    elif tab == "subscriptions":
        data["items"] = services.enrich_targets(db.rows("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created DESC", (uid,)))
    elif tab == "collections":
        cols = db.rows("SELECT * FROM user_collections WHERE user_id=? ORDER BY created DESC", (uid,))
        for c in cols:
            c["titles"] = services.enrich_targets(db.rows("SELECT * FROM collection_items WHERE collection_id=? ORDER BY created DESC", (c["id"],)))
        data["collections"] = cols
    elif tab in ("history", "watched-episodes"):
        where = "AND h.completed=1" if tab == "watched-episodes" else ""
        eps = db.rows(
            f"SELECT h.id, h.updated AS at, h.completed, s.title AS series_title, s.slug AS series_slug, "
            f"se.number AS season_no, e.number AS ep_no, e.title AS ep_title "
            f"FROM watch_history h JOIN episodes e ON e.id=h.episode_id JOIN seasons se ON se.id=e.season_id "
            f"JOIN series s ON s.id=se.series_id WHERE h.user_id=? AND h.target_type='EPISODE' {where} "
            f"ORDER BY h.updated DESC LIMIT 100", (uid,))
        entries = [{"id": r["id"], "at": r["at"],
                    "title": f"{r['series_title']} — S{r['season_no']}E{r['ep_no']} {r['ep_title']}",
                    "href": url_for("pages.episode", slug=r["series_slug"], season_no=r["season_no"], episode_no=r["ep_no"])}
                   for r in eps]
        if tab == "history":
            movies = db.rows(
                "SELECT h.id, h.updated AS at, m.title, m.slug FROM watch_history h JOIN movies m ON m.id=h.movie_id "
                "WHERE h.user_id=? AND h.target_type='MOVIE' ORDER BY h.updated DESC LIMIT 100", (uid,))
            entries += [{"id": r["id"], "at": r["at"], "title": r["title"], "href": url_for("pages.movie_detail", slug=r["slug"])} for r in movies]
            entries.sort(key=lambda e: e["at"], reverse=True)
            entries = entries[:50]
        data["entries"] = entries
    elif tab == "watched-movies":
        data["movies"] = db.rows(
            "SELECT m.* FROM watch_history h JOIN movies m ON m.id=h.movie_id "
            "WHERE h.user_id=? AND h.target_type='MOVIE' AND h.completed=1 ORDER BY h.updated DESC", (uid,))
    return render_template("library.html", tab=tab, tabs=LIBRARY_TABS, **data)


# ---- Profile ---------------------------------------------------------------------------

@bp.get("/profile")
def profile():
    user = current_user()
    if not user:
        return _login_redirect()
    uid = user["id"]
    me = db.get("users", uid)
    favorites = {f["rank"]: f for f in services.enrich_targets(db.rows("SELECT * FROM profile_favorites WHERE user_id=? ORDER BY rank", (uid,)))}
    watchlist = services.enrich_targets(db.rows("SELECT * FROM watchlist_items WHERE user_id=? ORDER BY created DESC", (uid,)))
    subs = services.enrich_targets(db.rows("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created DESC", (uid,)))
    cols = db.rows("SELECT * FROM user_collections WHERE user_id=? ORDER BY created DESC", (uid,))
    for c in cols:
        c["titles"] = services.enrich_targets(db.rows("SELECT * FROM collection_items WHERE collection_id=?", (c["id"],)))
    return render_template("profile.html", me=me, favorites=favorites, watchlist=watchlist, subs=subs, collections=cols,
                           all_series=_published_series(), all_movies=_published_movies())


@bp.get("/u/<username>")
def public_profile(username):
    profile = db.row("SELECT * FROM users WHERE username=?", (username,))
    if not profile or profile["is_banned"]:
        abort(404)
    favorites = {f["rank"]: f for f in services.enrich_targets(db.rows("SELECT * FROM profile_favorites WHERE user_id=? ORDER BY rank", (profile["id"],)))}
    return render_template("public_profile.html", profile=profile, favorites=favorites)


# ---- Forum -----------------------------------------------------------------------------

@bp.get("/forum")
def forum():
    cats = db.rows('SELECT * FROM forum_categories ORDER BY "order", name')
    for c in cats:
        c["thread_count"] = db.scalar("SELECT COUNT(*) FROM forum_threads WHERE category_id=?", (c["id"],))
    return render_template("forum.html", categories=cats)


@bp.get("/forum/<category_slug>")
def forum_category(category_slug):
    category = db.row("SELECT * FROM forum_categories WHERE slug=?", (category_slug,))
    if not category:
        abort(404)
    raw = db.rows("SELECT * FROM forum_threads WHERE category_id=? ORDER BY is_pinned DESC, created DESC LIMIT 200", (category["id"],))
    threads = services.enrich_users(raw, "user_id")
    for t in threads:
        t["post_count"] = db.scalar("SELECT COUNT(*) FROM forum_posts WHERE thread_id=?", (t["id"],))
    return render_template("forum_category.html", category=category, threads=threads)


@bp.get("/forum/<category_slug>/<thread_id>")
def forum_thread(category_slug, thread_id):
    thread = db.get("forum_threads", thread_id)
    category = db.row("SELECT * FROM forum_categories WHERE slug=?", (category_slug,))
    if not thread or not category or thread["category_id"] != category["id"]:
        abort(404)
    author = db.get("users", thread["user_id"])
    posts = services.enrich_users(db.rows("SELECT * FROM forum_posts WHERE thread_id=? ORDER BY created LIMIT 500", (thread_id,)), "user_id")
    return render_template("forum_thread.html", thread=thread, category=category, author=author, posts=posts)


# ---- Support ---------------------------------------------------------------------------

TICKET_STATUS = {"OPEN": "Offen", "IN_PROGRESS": "In Bearbeitung", "RESOLVED": "Gelöst", "CLOSED": "Geschlossen"}


@bp.get("/support")
def support():
    user = current_user()
    if not user:
        return _login_redirect()
    services.cleanup_closed_tickets()
    tickets = db.rows("SELECT * FROM tickets WHERE user_id=? ORDER BY created DESC", (user["id"],))
    return render_template("support.html", tickets=tickets, status_labels=TICKET_STATUS)


@bp.get("/support/<ticket_id>")
def support_ticket(ticket_id):
    user = current_user()
    if not user:
        return _login_redirect()
    services.cleanup_closed_tickets()
    ticket = db.get("tickets", ticket_id)
    is_staff = can.moderate(user["role"])
    if not ticket or (ticket["user_id"] != user["id"] and not is_staff):
        abort(404)
    messages = services.enrich_users(db.rows("SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created", (ticket_id,)), "sender_id")
    return render_template("ticket.html", ticket=ticket, messages=messages, is_staff=is_staff,
                           status_labels=TICKET_STATUS, back_url=url_for("admin_pages.tickets") if is_staff and ticket["user_id"] != user["id"] else url_for("pages.support"))
