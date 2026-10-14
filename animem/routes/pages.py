"""Öffentliche HTML-Seiten."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from datetime import datetime, timedelta, timezone

from .. import catalog, db, langs, notify, services, streamtools
from ..auth import can, current_user

bp = Blueprint("pages", __name__)


def _published_series():
    return db.rows("SELECT * FROM series WHERE status='PUBLISHED' ORDER BY title COLLATE NOCASE")


def _published_movies():
    return db.rows("SELECT * FROM movies WHERE status='PUBLISHED' ORDER BY title COLLATE NOCASE")


def _uid():
    user = current_user()
    return user["id"] if user else None


def _login_redirect():
    return redirect(url_for("auth_pages.login", next=request.path))


def _track_history(user, target_type, field, target_id):
    """Verlauf protokollieren (find-or-create); 'gesehen' setzt erst /api/watch/progress nach 3 Minuten."""
    existing = db.row(
        f"SELECT id FROM watch_history WHERE user_id=? AND target_type=? AND {field}=?", (user["id"], target_type, target_id)
    )
    if existing:
        db.update("watch_history", existing["id"], {})
    else:
        db.insert("watch_history", {"user_id": user["id"], "target_type": target_type, field: target_id,
                                    "progress_sec": 0, "completed": False})


def _pref_lang(user):
    return (db.scalar("SELECT pref_lang FROM users WHERE id=?", (user["id"],)) or "") if user else ""


# ---- Start, Listen, Suche --------------------------------------------------------------

@bp.get("/")
def home():
    uid = _uid()
    podium = services.ranking("alltime", 3)
    trending = services.ranking("trending", 6)
    latest = services.series_cards(
        db.rows("SELECT * FROM series WHERE status='PUBLISHED' ORDER BY created DESC LIMIT 12"), uid)
    resume = []
    if uid:
        rows = db.rows(
            "SELECT s.*, MAX(h.updated) AS last_seen FROM series s JOIN seasons se ON se.series_id = s.id "
            "JOIN episodes e ON e.season_id = se.id JOIN watch_history h ON h.episode_id = e.id AND h.user_id = ? "
            "AND h.target_type = 'EPISODE' WHERE s.status='PUBLISHED' GROUP BY s.id ORDER BY last_seen DESC LIMIT 24", (uid,))
        for c in services.series_cards(rows, uid):
            if c["state"] != "WATCHING":
                continue
            nxt = services.next_unwatched_episode(uid, c["season_id"])
            c["continue_href"] = f"/series/{c['slug']}/s/{c['season_no']}/e/{nxt['number']}" if nxt else c["href"]
            resume.append(c)
        resume = resume[:8]
    updated = [c for c in catalog.search_series({"sort": "updated"}, uid)[0][:8]]
    today = datetime.now(timezone.utc).date()
    soon = []
    for day in catalog.calendar(today, today + timedelta(days=3), uid):
        for item in day["items"]:
            soon.append({**item, "day": day["label"]})
    return render_template("home.html", top3=podium, trending=trending, latest=latest, resume=resume,
                           updated=updated, soon=soon[:6])


@bp.get("/series")
def series_list():
    params = {k: request.args.get(k, "") for k in ("q", "genre", "year", "lang", "status", "sort", "page")}
    cards, total, page, pages = catalog.search_series(params, _uid())
    active = sum(1 for k in ("genre", "year", "lang", "status") if params[k])
    return render_template("series_list.html", items=cards, total=total, page=page, pages=pages, params=params, active=active,
                           facets=catalog.facets(), sorts=catalog.SORTS, status_labels=catalog.STATUS_LABELS, lang_map=langs.LANGS,
                           lang_order=langs.ORDER)


@bp.get("/movies")
def movies_list():
    return render_template("movies_list.html", items=services.movie_cards(_published_movies()))


@bp.get("/ranking")
def ranking_page():
    tab = request.args.get("tab")
    if tab not in ("alltime", "trending"):
        tab = "alltime"
    return render_template("ranking.html", tab=tab, items=services.ranking(tab, 50),
                           min_votes=services.MIN_VOTES, days=services.TREND_DAYS)


@bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    series_rows = [s for s in _published_series() if catalog.matches(s, q)][:24]
    movie_rows = [m for m in _published_movies() if catalog.matches(m, q)][:24]
    cards = services.series_cards(series_rows, _uid())
    for c, row in zip(cards, series_rows):
        c["alt_hit"] = catalog.title_hit(row, q) if q else ""
    movies = services.movie_cards(movie_rows)
    for m, row in zip(movies, movie_rows):
        m["alt_hit"] = catalog.title_hit(row, q) if q else ""
    return render_template("search.html", q=q, series=cards, movies=movies)


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
        series=services.series_cards(services.find_by_taxonomy("series", field, item["id"]), _uid()),
        movies=services.movie_cards(services.find_by_taxonomy("movies", field, item["id"])),
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
    uid = user["id"] if user else None
    series = db.row("SELECT * FROM series WHERE slug=? AND status='PUBLISHED'", (slug,))
    if not series:
        abort(404)
    seasons = db.rows("SELECT * FROM seasons WHERE series_id=? ORDER BY number", (series["id"],))
    prog = services.progress_for(uid, [series["id"]]).get(series["id"])
    stats = {s["season_id"]: s for s in (prog["seasons"] if prog else [])}
    episode_ids = []
    for s in seasons:
        s["episodes"] = db.rows("SELECT * FROM episodes WHERE season_id=? AND status='PUBLISHED' ORDER BY number", (s["id"],))
        for e in s["episodes"]:
            e["langs"] = langs.ordered({x.get("lang") for x in (e["streams"] or []) if x.get("lang")})
        s["announced"] = db.rows("SELECT number, title, aired_at FROM episodes WHERE season_id=? AND status='DRAFT' AND aired_at<>'' "
                                 "ORDER BY number LIMIT 6", (s["id"],))
        episode_ids += [e["id"] for e in s["episodes"]]
        s["total"] = len(s["episodes"])
        s["watched"] = stats[s["id"]]["watched"] if s["id"] in stats else 0
        s["cover"] = s["thumbnail_url"] or series["thumbnail_url"]

    numbers = [s["number"] for s in seasons]
    requested = request.args.get("season", type=int)
    if requested in numbers:
        selected = requested
    elif prog:
        selected = prog["current"]["number"]
    else:
        selected = numbers[0] if numbers else None

    tags = services.taxonomy_items("tags", series["tag_ids"])
    genres = services.taxonomy_items("genres", series["genre_ids"])

    my = {}
    state = {"subscribed": False, "watchlist": False, "collections": [], "watched": set(), "sub": None, "prefs": None}
    if user:
        state["sub"] = db.row("SELECT * FROM subscriptions WHERE user_id=? AND series_id=?", (user["id"], series["id"]))
        state["prefs"] = db.row("SELECT pref_lang, notify_langs, notify_new_langs FROM users WHERE id=?", (user["id"],))
        for r in db.rows("SELECT season_id, value, comment FROM ratings WHERE user_id=? AND target_type='SEASON' "
                         "AND season_id IN (SELECT id FROM seasons WHERE series_id=?)", (user["id"], series["id"])):
            my[r["season_id"]] = r
        state["subscribed"] = bool(db.row("SELECT 1 AS x FROM subscriptions WHERE user_id=? AND series_id=?", (user["id"], series["id"])))
        state["watchlist"] = bool(db.row("SELECT 1 AS x FROM watchlist_items WHERE user_id=? AND series_id=?", (user["id"], series["id"])))
        state["collections"] = _collections_for(user, "series_id", series["id"])
        if episode_ids:
            marks = ",".join("?" for _ in episode_ids)
            state["watched"] = {r["episode_id"] for r in db.rows(
                f"SELECT episode_id FROM watch_history WHERE user_id=? AND target_type='EPISODE' AND completed=1 AND episode_id IN ({marks})",
                [user["id"]] + episode_ids)}

    season_data = [{
        "id": s["id"], "number": s["number"], "title": s["title"], "cover": s["cover"],
        "avg": s["avg_rating"] if s["ratings_count"] else None, "count": s["ratings_count"],
        "watched": s["watched"], "total": s["total"],
        "myRating": my.get(s["id"], {}).get("value"), "myComment": my.get(s["id"], {}).get("comment", ""),
    } for s in seasons]
    current = next((s for s in seasons if s["number"] == selected), None)
    my_current = my.get(current["id"], {}) if current else {}
    return render_template("series_detail.html", series=series, seasons=seasons, selected=selected, current=current,
                           season_data=season_data, my_current=my_current, tags=tags, genres=genres,
                           similar=catalog.similar_series(series, 6, uid), lang_map=langs.LANGS, lang_order=langs.ORDER,
                           status_label=catalog.STATUS_LABELS.get(series["air_status"], ""),
                           progress_state=prog["state"] if prog else "NOT_STARTED", **state)


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

    if user:
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
    pref = _pref_lang(user)
    streams = streamtools.player_streams(ep, "EPISODE", pref)
    return render_template("episode.html", series=series, season=season, ep=ep, streams=streams, next_url=next_url,
                           pref_lang=streamtools.default_language(streams, pref), lang_list=streamtools.languages_of(streams),
                           lang_map=langs.LANGS, target_type="EPISODE",
                           season_url=url_for("pages.series_detail", slug=slug, season=season_no))


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
    pref = _pref_lang(user)
    streams = streamtools.player_streams(movie, "MOVIE", pref)
    return render_template("movie_detail.html", movie=movie, streams=streams, pref_lang=streamtools.default_language(streams, pref),
                           lang_list=streamtools.languages_of(streams), lang_map=langs.LANGS, target_type="MOVIE",
                           tags=services.taxonomy_items("tags", movie["tag_ids"]),
                           genres=services.taxonomy_items("genres", movie["genre_ids"]), **state)


# ---- Bibliothek ------------------------------------------------------------------------

LIBRARY_TABS = [
    ("watchlist", "Watchlist"), ("watching", "Schaue ich gerade"), ("completed", "Abgeschlossen"),
    ("subscriptions", "Abonniert"), ("history", "Verlauf"),
    ("watched-episodes", "Gesehene Folgen"), ("watched-movies", "Gesehene Filme"), ("collections", "Sammlungen"),
]


def _tracked_series_cards(uid):
    """Alle Serien, bei denen der Nutzer schon mindestens eine Folge geöffnet hat (zuletzt gesehen zuerst)."""
    rows = db.rows(
        "SELECT s.*, MAX(h.updated) AS last_seen FROM series s JOIN seasons se ON se.series_id = s.id "
        "JOIN episodes e ON e.season_id = se.id JOIN watch_history h ON h.episode_id = e.id AND h.user_id = ? "
        "AND h.target_type = 'EPISODE' WHERE s.status='PUBLISHED' GROUP BY s.id ORDER BY last_seen DESC", (uid,))
    return services.series_cards(rows, uid)


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
        data["items"] = services.target_cards(services.enrich_targets(
            db.rows("SELECT * FROM watchlist_items WHERE user_id=? ORDER BY created DESC", (uid,))), uid)
    elif tab == "subscriptions":
        data["items"] = services.target_cards(services.enrich_targets(
            db.rows("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created DESC", (uid,))), uid)
    elif tab in ("watching", "completed"):
        wanted = "WATCHING" if tab == "watching" else "COMPLETED"
        cards = [c for c in _tracked_series_cards(uid) if c["state"] == wanted]
        for c in cards:
            nxt = services.next_unwatched_episode(uid, c["season_id"]) if wanted == "WATCHING" else None
            c["continue_href"] = f"/series/{c['slug']}/s/{c['season_no']}/e/{nxt['number']}" if nxt else None
        data["items"] = cards
    elif tab == "collections":
        cols = db.rows("SELECT * FROM user_collections WHERE user_id=? ORDER BY created DESC", (uid,))
        for c in cols:
            c["titles"] = services.target_cards(services.enrich_targets(
                db.rows("SELECT * FROM collection_items WHERE collection_id=? ORDER BY created DESC", (c["id"],))), uid)
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
        data["movies"] = services.movie_cards(db.rows(
            "SELECT m.* FROM watch_history h JOIN movies m ON m.id=h.movie_id "
            "WHERE h.user_id=? AND h.target_type='MOVIE' AND h.completed=1 ORDER BY h.updated DESC", (uid,)))
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
    watchlist = services.target_cards(services.enrich_targets(
        db.rows("SELECT * FROM watchlist_items WHERE user_id=? ORDER BY created DESC", (uid,))), uid)
    subs = services.target_cards(services.enrich_targets(
        db.rows("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created DESC", (uid,))), uid)
    cols = db.rows("SELECT * FROM user_collections WHERE user_id=? ORDER BY created DESC", (uid,))
    for c in cols:
        c["count"] = db.scalar("SELECT COUNT(*) FROM collection_items WHERE collection_id=?", (c["id"],))
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


# ---- Benachrichtigungen ----------------------------------------------------------------------

@bp.get("/notifications")
def notifications_page():
    user = current_user()
    if not user:
        return _login_redirect()
    items = db.rows("SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 100", (user["id"],))
    return render_template("notifications.html", items=items, unread=notify.unread_count(user["id"]))


@bp.get("/notifications/go/<notification_id>")
def notification_go(notification_id):
    """Markiert eine Meldung als gelesen und leitet zum Ziel weiter (funktioniert auch ohne JavaScript)."""
    user = current_user()
    if not user:
        return _login_redirect()
    n = db.get("notifications", notification_id)
    if not n or n["user_id"] != user["id"]:
        abort(404)
    notify.mark_read(user["id"], [n["id"]])
    link = n["link"] if n["link"].startswith("/") and not n["link"].startswith("//") else "/notifications"
    return redirect(link)


# ---- Erscheinungskalender --------------------------------------------------------------------

@bp.get("/calendar")
def calendar_page():
    user = current_user()
    today = datetime.now(timezone.utc).date()
    mine = request.args.get("mine") == "1" and bool(user)
    days = catalog.calendar(today - timedelta(days=7), today + timedelta(days=28), user["id"] if user else None, mine)
    upcoming = [d for d in days if not d["past"]]
    recent = [d for d in days if d["past"]][::-1]
    return render_template("calendar.html", upcoming=upcoming, recent=recent, mine=mine)
