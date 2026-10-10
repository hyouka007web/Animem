"""/api/users/*, /api/admin/settings, /api/admin/forum/*."""
import sqlite3

from flask import Blueprint, request

from .. import auth, db, security, services, validation
from ..auth import assignable_roles, can, can_manage_target_role, current_user, role_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_admin", __name__)


def _json():
    return request.get_json(silent=True)


def _limit(scope, limit, window):
    return security.rate_limit(scope, limit, window, key=current_user()["id"])


# ======================================================================================
# Nutzerverwaltung
# ======================================================================================

@bp.patch("/api/users/<user_id>/role")
@role_required(can.manage_admins)
def user_role(user_id):
    actor = current_user()
    if user_id == actor["id"]:
        return fail("Du kannst deine eigene Rolle nicht ändern.", 403)
    allowed, retry = _limit("role-change", 20, 600)
    if not allowed:
        return limited_response(retry)
    data = _json()
    role = data.get("role") if isinstance(data, dict) else None
    if role not in ("USER", "ADMIN", "HEAD_ADMIN", "OWNER"):
        return fail("Ungültige Rolle.")
    target = db.get("users", user_id)
    if not target:
        return fail("Nutzer nicht gefunden", 404)
    if not can_manage_target_role(actor["role"], target["role"]):
        return fail("Diese Rolle darfst du nicht bearbeiten.", 403)
    if role not in assignable_roles(actor["role"]):
        return fail("Diese Rolle darfst du nicht vergeben.", 403)
    db.update("users", user_id, {"role": role})
    services.audit(actor["id"], "USER_ROLE_CHANGED", "USER", user_id, {"role": role, "previous": target["role"]})
    return ok({"id": user_id, "role": role})


@bp.patch("/api/users/<user_id>/status")
@role_required(can.manage_admins)
def user_status(user_id):
    actor = current_user()
    if user_id == actor["id"]:
        return fail("Du kannst dich nicht selbst sperren.", 403)
    allowed, retry = _limit("user-status", 30, 600)
    if not allowed:
        return limited_response(retry)
    data = _json()
    banned = data.get("isBanned") if isinstance(data, dict) else None
    if not isinstance(banned, bool):
        return fail("Ungültiger Nutzerstatus.")
    target = db.get("users", user_id)
    if not target:
        return fail("Nutzer nicht gefunden.", 404)
    if not can_manage_target_role(actor["role"], target["role"]):
        return fail("Dieser Nutzer darf nicht bearbeitet werden.", 403)
    with db.transaction():
        db.update("users", user_id, {"is_banned": banned})
        if banned:
            db.run("DELETE FROM sessions WHERE user_id=?", (user_id,))  # gesperrte Nutzer sofort abmelden
    services.audit(actor["id"], "USER_BANNED" if banned else "USER_UNBANNED", "USER", user_id)
    return ok({"id": user_id, "is_banned": banned})


# ======================================================================================
# Einstellungen
# ======================================================================================

SETTING_KEYS = ("site_name", "registration_open", "maintenance_mode")


@bp.get("/api/admin/settings")
@role_required(can.manage_settings)
def settings_get():
    settings = db.all_settings()
    return ok([{"key": k, "value": settings[k]} for k in SETTING_KEYS])


@bp.patch("/api/admin/settings")
@role_required(can.manage_settings)
def settings_set():
    actor = current_user()
    allowed, retry = _limit("settings", 30, 600)
    if not allowed:
        return limited_response(retry)
    data = _json()
    key = data.get("key") if isinstance(data, dict) else None
    value = data.get("value") if isinstance(data, dict) else None
    if key not in SETTING_KEYS:
        return fail("Ungültige Einstellung.")
    if key == "site_name":
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 60:
            return fail("Der Seitenname muss 1 bis 60 Zeichen lang sein.")
        value = value.strip()
    elif not isinstance(value, bool):
        return fail("Ungültige Einstellung.")
    db.set_setting(key, value)
    services.audit(actor["id"], "SETTING_CHANGED", "SETTING", key, {"value": value})
    return ok({"key": key, "value": value})


# ======================================================================================
# Forum-Moderation & Kategorien
# ======================================================================================

@bp.patch("/api/admin/forum/threads/<thread_id>")
@role_required(can.moderate)
def forum_thread_moderate(thread_id):
    actor = current_user()
    allowed, retry = _limit("forum-moderate", 60, 60)
    if not allowed:
        return limited_response(retry)
    data = _json()
    changes = {}
    if isinstance(data, dict):
        for src, col in (("isPinned", "is_pinned"), ("isLocked", "is_locked")):
            if isinstance(data.get(src), bool):
                changes[col] = data[src]
    if not changes:
        return fail("Ungültige Moderationsdaten.")
    thread = db.update("forum_threads", thread_id, changes)
    if not thread:
        return fail("Thread nicht gefunden.", 404)
    services.audit(actor["id"], "FORUM_THREAD_MODERATED", "FORUM_THREAD", thread_id, changes)
    return ok(thread)


@bp.delete("/api/admin/forum/threads/<thread_id>")
@role_required(can.moderate)
def forum_thread_delete(thread_id):
    thread = db.get("forum_threads", thread_id)
    if not thread:
        return fail("Thread nicht gefunden.", 404)
    db.delete("forum_threads", thread_id)  # Beiträge folgen per CASCADE
    services.audit(current_user()["id"], "FORUM_THREAD_DELETED", "FORUM_THREAD", thread_id, {"title": thread["title"]})
    return ok()


@bp.post("/api/admin/forum/categories")
@role_required(can.moderate)
def forum_category_create():
    try:
        data = validation.as_dict(_json())
        name = validation.text(data, "name", min=2, max=60, label="Name")
        description = validation.text(data, "description", max=300, label="Beschreibung")
    except validation.ValidationError as exc:
        return fail(str(exc))
    position = (db.scalar('SELECT COALESCE(MAX("order"), -1) + 1 FROM forum_categories') or 0)
    try:
        cat = db.insert("forum_categories", {
            "name": name, "slug": services.unique_slug("forum_categories", name), "description": description, "order": position,
        })
    except sqlite3.IntegrityError:
        return fail("Diese Kategorie existiert bereits.")
    services.audit(current_user()["id"], "FORUM_CATEGORY_CREATED", "FORUM_CATEGORY", cat["id"], {"name": name})
    return ok(cat, 201)


@bp.delete("/api/admin/forum/categories/<category_id>")
@role_required(can.manage_admins)
def forum_category_delete(category_id):
    cat = db.get("forum_categories", category_id)
    if not cat:
        return fail("Kategorie nicht gefunden.", 404)
    db.delete("forum_categories", category_id)  # Threads & Beiträge folgen per CASCADE
    services.audit(current_user()["id"], "FORUM_CATEGORY_DELETED", "FORUM_CATEGORY", category_id, {"name": cat["name"]})
    return ok()
