"""Benachrichtigungen, Sprach-Einstellungen und Abo-Einstellungen."""
from flask import Blueprint, request

from .. import db, notify, validation
from ..auth import current_user, login_required
from ..langs import ALL, LANGS
from ..security import fail, ok

bp = Blueprint("api_notify", __name__)


def _json():
    return request.get_json(silent=True)


def _lang_list(value):
    if not isinstance(value, list) or any(l not in LANGS for l in value):
        raise validation.ValidationError("Ungültige Sprachauswahl.")
    return [l for l in ALL if l in value]


# ---- Meldungen ---------------------------------------------------------------------------

@bp.get("/api/notifications")
@login_required
def list_notifications():
    uid = current_user()["id"]
    unread = request.args.get("unread") == "1"
    rows = db.rows(f"SELECT id, type, message, link, is_read, created FROM notifications WHERE user_id=? {'AND is_read=0' if unread else ''} "
                   "ORDER BY created DESC LIMIT 100", (uid,))
    return ok({"items": rows, "unread": notify.unread_count(uid)})


@bp.post("/api/notifications/read")
@login_required
def read_notifications():
    data = _json() if request.is_json else {}
    ids = data.get("ids") if isinstance(data, dict) else None
    if ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        return fail("Ungültige Anfrage.")
    notify.mark_read(current_user()["id"], ids or None)
    return ok({"unread": notify.unread_count(current_user()["id"])})


@bp.delete("/api/notifications")
@login_required
def delete_notifications():
    uid = current_user()["id"]
    data = _json() if request.is_json else {}
    ids = data.get("ids") if isinstance(data, dict) else None
    if ids:
        marks = ",".join("?" for _ in ids)
        db.run(f"DELETE FROM notifications WHERE user_id=? AND id IN ({marks})", [uid, *ids])
    else:
        db.run("DELETE FROM notifications WHERE user_id=? AND is_read=1", (uid,))
    return ok({"unread": notify.unread_count(uid)})


# ---- Einstellungen des Nutzers --------------------------------------------------------------

@bp.patch("/api/profile/preferences")
@login_required
def preferences():
    uid = current_user()["id"]
    data = _json()
    if not isinstance(data, dict):
        return fail("Ungültige Anfrage.")
    changes = {}
    try:
        if "prefLang" in data:
            if data["prefLang"] not in ("", *ALL):
                raise validation.ValidationError("Ungültige Sprache.")
            changes["pref_lang"] = data["prefLang"]
        if "notifyLangs" in data:
            changes["notify_langs"] = _lang_list(data["notifyLangs"])
        if "notifyNewLangs" in data:
            if not isinstance(data["notifyNewLangs"], bool):
                raise validation.ValidationError("Ungültige Einstellung.")
            changes["notify_new_langs"] = data["notifyNewLangs"]
    except validation.ValidationError as exc:
        return fail(str(exc))
    if not changes:
        return fail("Nichts zu speichern.")
    db.update("users", uid, changes)
    return ok({"success": True})


@bp.patch("/api/subscriptions/settings")
@login_required
def subscription_settings():
    """Pro Serie: 'default' (wie im Profil), 'custom' (eigene Sprachen) oder 'mute' (keine Meldungen)."""
    uid = current_user()["id"]
    data = _json()
    if not isinstance(data, dict) or not isinstance(data.get("seriesId"), str):
        return fail("Ungültige Anfrage.")
    sub = db.row("SELECT * FROM subscriptions WHERE user_id=? AND series_id=?", (uid, data["seriesId"]))
    if not sub:
        return fail("Du hast diese Serie nicht abonniert.", 404)
    mode = data.get("mode")
    try:
        if mode == "default":
            changes = {"notify_on_new_episode": True, "notify_langs": None}
        elif mode == "mute":
            changes = {"notify_on_new_episode": False}
        elif mode == "custom":
            langs = _lang_list(data.get("langs"))
            if not langs:
                raise validation.ValidationError("Bitte mindestens eine Sprache wählen oder die Serie stummschalten.")
            changes = {"notify_on_new_episode": True, "notify_langs": langs}
        else:
            raise validation.ValidationError("Ungültiger Modus.")
    except validation.ValidationError as exc:
        return fail(str(exc))
    db.update("subscriptions", sub["id"], changes)
    return ok({"success": True})
