"""/api/watchlist, /api/subscriptions, /api/collections, /api/forum, /api/tickets."""
import sqlite3

from flask import Blueprint, redirect, request

from .. import db, security, services, validation
from ..auth import can, current_user, login_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_social", __name__)


def _json():
    return request.get_json(silent=True)


def _limit(scope, limit, window):
    return security.rate_limit(scope, limit, window, key=current_user()["id"])


def _target_table(field):
    return "series" if field == "series_id" else "movies"


# ======================================================================================
# Watchlist
# ======================================================================================

@bp.get("/api/watchlist")
@login_required
def watchlist_list():
    raw = db.rows("SELECT * FROM watchlist_items WHERE user_id=? ORDER BY created DESC LIMIT 200", (current_user()["id"],))
    return ok(services.enrich_targets(raw))


@bp.post("/api/watchlist")
@login_required
def watchlist_add():
    user = current_user()
    allowed, retry = _limit("watchlist", 30, 60)
    if not allowed:
        return limited_response(retry)
    try:
        field, value = validation.one_target(_json())
    except validation.ValidationError as exc:
        return fail(str(exc))
    if not db.get(_target_table(field), value):
        return fail("Ziel nicht gefunden.", 404)
    existing = db.row(f"SELECT * FROM watchlist_items WHERE user_id=? AND {field}=?", (user["id"], value))
    if existing:
        return ok(existing)
    try:
        return ok(db.insert("watchlist_items", {"user_id": user["id"], field: value}), 201)
    except sqlite3.IntegrityError:
        return ok(db.row(f"SELECT * FROM watchlist_items WHERE user_id=? AND {field}=?", (user["id"], value)))


@bp.delete("/api/watchlist")
@login_required
def watchlist_remove():
    try:
        field, value = validation.one_target(_json())
    except validation.ValidationError:
        return fail("Ungültiges Watchlist-Ziel.")
    db.run(f"DELETE FROM watchlist_items WHERE user_id=? AND {field}=?", (current_user()["id"], value))
    return ok()


# ======================================================================================
# Abos
# ======================================================================================

@bp.get("/api/subscriptions")
@login_required
def subscriptions_list():
    raw = db.rows("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created DESC LIMIT 200", (current_user()["id"],))
    return ok(services.enrich_targets(raw))


def _series_id_from_body():
    data = _json()
    sid = data.get("seriesId") if isinstance(data, dict) else None
    if not isinstance(sid, str) or not sid or len(sid) > 64:
        return None
    return sid


@bp.post("/api/subscriptions")
@login_required
def subscriptions_add():
    user = current_user()
    allowed, retry = _limit("subscriptions", 30, 60)
    if not allowed:
        return limited_response(retry)
    sid = _series_id_from_body()
    if not sid:
        return fail("Ungültige Serie.")
    if not db.get("series", sid):
        return fail("Serie nicht gefunden.", 404)
    existing = db.row("SELECT * FROM subscriptions WHERE user_id=? AND series_id=?", (user["id"], sid))
    if existing:
        return ok(existing)
    try:
        return ok(db.insert("subscriptions", {"user_id": user["id"], "series_id": sid, "notify_on_new_episode": True}), 201)
    except sqlite3.IntegrityError:
        return ok(db.row("SELECT * FROM subscriptions WHERE user_id=? AND series_id=?", (user["id"], sid)))


@bp.delete("/api/subscriptions")
@login_required
def subscriptions_remove():
    sid = _series_id_from_body()
    if not sid:
        return fail("Ungültige Serie.")
    db.run("DELETE FROM subscriptions WHERE user_id=? AND series_id=?", (current_user()["id"], sid))
    return ok()


# ======================================================================================
# Sammlungen
# ======================================================================================

def _owned_collection(collection_id):
    c = db.get("user_collections", collection_id) if isinstance(collection_id, str) else None
    return c if c and c["user_id"] == current_user()["id"] else None


@bp.get("/api/collections")
@login_required
def collections_list():
    return ok(db.rows("SELECT * FROM user_collections WHERE user_id=? ORDER BY created DESC", (current_user()["id"],)))


@bp.post("/api/collections")
@login_required
def collections_create():
    user = current_user()
    allowed, retry = _limit("collection-create", 20, 60)
    if not allowed:
        return limited_response(retry)
    try:
        data = validation.as_dict(_json())
        title = validation.text(data, "title", min=1, max=120, label="Titel")
        description = validation.text(data, "description", max=1000, label="Beschreibung")
    except validation.ValidationError:
        return fail("Ungültige Sammlungsdaten.")
    return ok(db.insert("user_collections", {"user_id": user["id"], "title": title, "description": description}), 201)


@bp.delete("/api/collections/<collection_id>")
@login_required
def collections_delete(collection_id):
    if not _owned_collection(collection_id):
        return fail("Sammlung nicht gefunden.", 404)
    db.delete("user_collections", collection_id)
    return ok()


def _collection_item_args():
    data = _json()
    field, value = validation.one_target(data)
    return data.get("collectionId"), field, value


@bp.post("/api/collections/items")
@login_required
def collection_item_add():
    allowed, retry = _limit("collection-item", 40, 60)
    if not allowed:
        return limited_response(retry)
    try:
        collection_id, field, value = _collection_item_args()
    except validation.ValidationError:
        return fail("Ungültige Anfrage.")
    collection = _owned_collection(collection_id)
    if not collection:
        return fail("Sammlung nicht gefunden.", 404)
    if not db.get(_target_table(field), value):
        return fail("Ziel nicht gefunden.", 404)
    existing = db.row(f"SELECT * FROM collection_items WHERE collection_id=? AND {field}=?", (collection["id"], value))
    if existing:
        return ok(existing)
    return ok(db.insert("collection_items", {"collection_id": collection["id"], field: value}), 201)


@bp.delete("/api/collections/items")
@login_required
def collection_item_remove():
    try:
        collection_id, field, value = _collection_item_args()
    except validation.ValidationError:
        return fail("Ungültige Anfrage.")
    collection = _owned_collection(collection_id)
    if not collection:
        return fail("Sammlung nicht gefunden.", 404)
    db.run(f"DELETE FROM collection_items WHERE collection_id=? AND {field}=?", (collection["id"], value))
    return ok()


# ======================================================================================
# Forum
# ======================================================================================

@bp.get("/api/forum/threads")
def forum_threads():
    slug = request.args.get("category")
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(50, max(1, int(request.args.get("limit", 25))))
    except ValueError:
        page, limit = 1, 25
    args, where = [], ""
    if slug:
        cat = db.row("SELECT id FROM forum_categories WHERE slug=?", (slug,))
        if not cat:
            return ok({"items": [], "page": page, "perPage": limit, "totalItems": 0, "totalPages": 1})
        where, args = "WHERE category_id=?", [cat["id"]]
    total = db.scalar(f"SELECT COUNT(*) FROM forum_threads {where}", args)
    items = db.rows(
        f"SELECT * FROM forum_threads {where} ORDER BY is_pinned DESC, created DESC LIMIT ? OFFSET ?",
        args + [limit, (page - 1) * limit],
    )
    out = []
    for t in services.enrich_users(items, "user_id"):
        u = t.pop("user")
        t["user"] = {"username": u["username"]} if u else None
        t["postCount"] = db.scalar("SELECT COUNT(*) FROM forum_posts WHERE thread_id=?", (t["id"],))
        out.append(t)
    return ok({"items": out, "page": page, "perPage": limit, "totalItems": total, "totalPages": max(1, -(-total // limit))})


@bp.post("/api/forum/threads")
@login_required
def forum_thread_create():
    user = current_user()
    allowed, retry = _limit("forum-thread", 3, 600)
    if not allowed:
        return limited_response(retry)
    try:
        data = validation.as_dict(_json())
        category_id = validation.text(data, "categoryId", min=1, max=64)
        title = validation.text(data, "title", min=3, max=160, label="Titel")
        content = validation.text(data, "content", min=1, max=5000, label="Beitrag")
    except validation.ValidationError as exc:
        return fail(str(exc))
    if not db.get("forum_categories", category_id):
        return fail("Kategorie nicht gefunden", 404)
    with db.transaction():
        thread = db.insert("forum_threads", {"category_id": category_id, "user_id": user["id"], "title": title})
        db.insert("forum_posts", {"thread_id": thread["id"], "user_id": user["id"], "content": content})
    return ok(thread, 201)


@bp.post("/api/forum/posts")
@login_required
def forum_post_create():
    user = current_user()
    allowed, retry = _limit("forum-post", 10, 60)
    if not allowed:
        return limited_response(retry)
    try:
        data = validation.as_dict(_json())
        thread_id = validation.text(data, "threadId", min=1, max=64)
        content = validation.text(data, "content", min=1, max=5000, label="Beitrag")
    except validation.ValidationError as exc:
        return fail(str(exc))
    thread = db.get("forum_threads", thread_id)
    if not thread:
        return fail("Thread nicht gefunden", 404)
    if thread["is_locked"]:
        return fail("Dieser Thread ist gesperrt", 403)
    post = db.insert("forum_posts", {"thread_id": thread["id"], "user_id": user["id"], "content": content})
    db.update("forum_threads", thread["id"], {})
    profile = db.get("users", user["id"])
    return ok({**post, "user": {"username": profile["username"], "avatar_url": profile["avatar_url"] or None}}, 201)


# ======================================================================================
# Support-Tickets
# ======================================================================================

@bp.get("/api/tickets")
@login_required
def tickets_list():
    user = current_user()
    services.cleanup_closed_tickets()
    if can.moderate(user["role"]):
        raw = db.rows("SELECT * FROM tickets ORDER BY updated DESC LIMIT 100")
    else:
        raw = db.rows("SELECT * FROM tickets WHERE user_id=? ORDER BY updated DESC LIMIT 100", (user["id"],))
    out = []
    for t in services.enrich_users(raw, "user_id"):
        u = t.pop("user")
        t["user"] = {"username": u["username"]} if u else None
        t["messageCount"] = db.scalar("SELECT COUNT(*) FROM ticket_messages WHERE ticket_id=?", (t["id"],))
        out.append(t)
    return ok(out)


@bp.post("/api/tickets")
@login_required
def ticket_create():
    user = current_user()
    allowed, retry = _limit("tickets", 5, 15 * 60)
    if not allowed:
        return limited_response(retry)
    is_form = not request.is_json
    data = request.form.to_dict() if is_form else _json()
    try:
        data = validation.as_dict(data)
        subject = validation.text(data, "subject", min=3, max=160, label="Betreff")
        message = validation.text(data, "message", min=1, max=5000, label="Nachricht")
        priority = validation.choice(data, "priority", ("LOW", "MEDIUM", "HIGH", "URGENT"), "MEDIUM", "Priorität")
    except validation.ValidationError as exc:
        return fail(str(exc))
    with db.transaction():
        ticket = db.insert("tickets", {"user_id": user["id"], "subject": subject, "priority": priority, "status": "OPEN"})
        db.insert("ticket_messages", {"ticket_id": ticket["id"], "sender_id": user["id"], "content": message, "is_staff": False})
    if is_form:
        return redirect("/support", 303)
    return ok(ticket, 201)


@bp.patch("/api/tickets/<ticket_id>")
@login_required
def ticket_status(ticket_id):
    user = current_user()
    if not can.moderate(user["role"]):
        return fail("Nicht berechtigt", 403)
    allowed, retry = _limit("ticket-status", 60, 60)
    if not allowed:
        return limited_response(retry)
    data = _json()
    status = data.get("status") if isinstance(data, dict) else None
    if status not in ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"):
        return fail("Ungültiger Status.")
    ticket = db.update("tickets", ticket_id, {"status": status})
    return ok(ticket) if ticket else fail("Ticket nicht gefunden", 404)


def _visible_ticket(ticket_id):
    user = current_user()
    ticket = db.get("tickets", ticket_id)
    if not ticket:
        return None, fail("Ticket nicht gefunden", 404)
    if not can.moderate(user["role"]) and ticket["user_id"] != user["id"]:
        return None, fail("Nicht berechtigt", 403)
    return ticket, None


@bp.get("/api/tickets/<ticket_id>/messages")
@login_required
def ticket_messages(ticket_id):
    ticket, err = _visible_ticket(ticket_id)
    if err:
        return err
    raw = db.rows("SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created LIMIT 500", (ticket["id"],))
    out = []
    for m in services.enrich_users(raw, "sender_id"):
        u = m.pop("user")
        out.append({**m, "sender": {"username": u["username"]} if u else None})
    return ok(out)


@bp.post("/api/tickets/<ticket_id>/messages")
@login_required
def ticket_message_create(ticket_id):
    user = current_user()
    allowed, retry = _limit("ticket-message", 15, 60)
    if not allowed:
        return limited_response(retry)
    try:
        content = validation.text(validation.as_dict(_json()), "content", min=1, max=5000, label="Nachricht")
    except validation.ValidationError:
        return fail("Nachricht fehlt oder ist zu lang.")
    ticket, err = _visible_ticket(ticket_id)
    if err:
        return err
    is_staff = can.moderate(user["role"])
    if ticket["status"] == "CLOSED" and not is_staff:
        return fail("Dieses Ticket ist geschlossen.", 403)
    with db.transaction():
        msg = db.insert("ticket_messages", {"ticket_id": ticket["id"], "sender_id": user["id"], "content": content, "is_staff": is_staff})
        # Staff-Antwort -> "In Bearbeitung"; Antwort des Nutzers auf ein gelöstes Ticket öffnet es wieder.
        if is_staff:
            db.update("tickets", ticket["id"], {"status": "IN_PROGRESS"})
        elif ticket["status"] == "RESOLVED":
            db.update("tickets", ticket["id"], {"status": "OPEN"})
        else:
            db.update("tickets", ticket["id"], {})
    return ok(msg, 201)
