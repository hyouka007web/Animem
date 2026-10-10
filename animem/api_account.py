"""/api/profile, /api/profile/favorites, /api/profile/totp, /api/profile/sessions."""
import sqlite3

from flask import Blueprint, redirect, request

from .. import auth, db, security, validation
from ..auth import current_user, login_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_account", __name__)


def _json():
    return request.get_json(silent=True)


def _limit(scope, limit, window):
    return security.rate_limit(scope, limit, window, key=current_user()["id"])


# ======================================================================================
# Profil
# ======================================================================================

@bp.route("/api/profile", methods=["PATCH", "POST"])
@login_required
def update_profile():
    user = current_user()
    allowed, retry = _limit("profile", 10, 600)
    if not allowed:
        return limited_response(retry)
    is_form = not request.is_json
    data = request.form.to_dict() if is_form else _json()
    try:
        data = validation.as_dict(data)
        fields = {
            "avatar_url": validation.media_url(data.get("avatarUrl"), optional=True, label="Avatar"),
            "banner_url": validation.media_url(data.get("bannerUrl"), optional=True, label="Banner"),
            "bio": validation.text(data, "bio", max=500, label="Bio"),
            "display_name": validation.text(data, "displayName", max=64, label="Anzeigename"),
        }
    except validation.ValidationError as exc:
        return fail(str(exc))
    try:
        record = db.update("users", user["id"], fields)
    except sqlite3.IntegrityError:
        return fail("Dieser Anzeigename ist bereits vergeben.", 409)
    if is_form:
        return redirect("/profile", 303)
    record.pop("password_hash", None)
    record.pop("totp_secret", None)
    record.pop("totp_recovery_codes", None)
    return ok(record)


@bp.post("/api/profile/favorites")
@login_required
def favorite_set():
    user = current_user()
    allowed, retry = _limit("favorites", 20, 60)
    if not allowed:
        return limited_response(retry)
    data = _json()
    try:
        rank = validation.integer(validation.as_dict(data), "rank", min=1, max=3)
        field, value = validation.one_target(data)
    except validation.ValidationError:
        return fail("Genau ein gültiges Profil-Favorit-Ziel ist erforderlich.")
    table = "series" if field == "series_id" else "movies"
    target = db.get(table, value)
    if not target or target["status"] != "PUBLISHED":
        return fail("Favorit nicht gefunden.", 404)
    payload = {"series_id": value if field == "series_id" else None, "movie_id": value if field == "movie_id" else None}
    with db.transaction():
        existing = db.row("SELECT * FROM profile_favorites WHERE user_id=? AND rank=?", (user["id"], rank))
        if existing:
            rec = db.update("profile_favorites", existing["id"], payload)
        else:
            rec = db.insert("profile_favorites", {"user_id": user["id"], "rank": rank, **payload})
    return ok(rec)


@bp.delete("/api/profile/favorites")
@login_required
def favorite_remove():
    data = _json()
    rank = data.get("rank") if isinstance(data, dict) else None
    if rank not in (1, 2, 3):
        return fail("Ungültiger Platz")
    db.run("DELETE FROM profile_favorites WHERE user_id=? AND rank=?", (current_user()["id"], rank))
    return ok()


# ======================================================================================
# Zwei-Faktor-Authentifizierung
# ======================================================================================

@bp.post("/api/profile/totp")
@login_required
def totp_setup():
    user = current_user()
    allowed, retry = _limit("totp-setup", 5, 900)
    if not allowed:
        return limited_response(retry)
    if user["two_factor_enabled"]:
        return fail("2FA ist bereits aktiv. Zum Neueinrichten zuerst deaktivieren.", 409)
    secret = security.totp_secret()
    codes = security.recovery_codes()
    db.update("users", user["id"], {
        "totp_secret": secret, "totp_enabled": False,
        "totp_recovery_codes": [security.sha256(c) for c in codes],
    })
    return ok({"secret": secret, "otpauthUri": security.otpauth_uri(secret, user["username"]), "recoveryCodes": codes})


@bp.patch("/api/profile/totp")
@login_required
def totp_enable():
    user = current_user()
    allowed, retry = _limit("totp-enable", 10, 900)
    if not allowed:
        return limited_response(retry)
    data = _json()
    code = str(data.get("code") or "").strip() if isinstance(data, dict) else ""
    if len(code) != 6:
        return fail("Ungültiger Code.")
    secret = db.scalar("SELECT totp_secret FROM users WHERE id=?", (user["id"],))
    if not secret:
        return fail("Zuerst die Einrichtung starten.")
    if not security.verify_totp(secret, code):
        return fail("Der Code ist ungültig.")
    db.update("users", user["id"], {"totp_enabled": True})
    return ok()


@bp.delete("/api/profile/totp")
@login_required
def totp_disable():
    user = current_user()
    allowed, retry = _limit("totp-disable", 10, 900)
    if not allowed:
        return limited_response(retry)
    data = _json()
    code = str(data.get("code") or "").strip() if isinstance(data, dict) else ""
    if not 6 <= len(code) <= 64:
        return fail("Ungültiger Code.")
    rec = db.row("SELECT totp_secret, totp_recovery_codes FROM users WHERE id=?", (user["id"],))
    valid = bool(rec["totp_secret"] and security.verify_totp(rec["totp_secret"], code)) or \
        security.sha256(code.lower()) in (rec["totp_recovery_codes"] or [])
    if not valid:
        return fail("Der Code ist ungültig.")
    db.update("users", user["id"], {"totp_enabled": False, "totp_secret": None, "totp_recovery_codes": []})
    return ok()


# ======================================================================================
# Aktive Sitzungen
# ======================================================================================

@bp.get("/api/profile/sessions")
@login_required
def sessions_list():
    user = current_user()
    token = request.cookies.get(auth.SESSION_COOKIE)
    current_hash = security.sha256(token) if token else None
    rows = db.rows(
        "SELECT * FROM sessions WHERE user_id=? AND pending_2fa=0 AND expires_at > ? ORDER BY last_seen DESC",
        (user["id"], db.utcnow()),
    )
    return ok([{
        "id": s["id"], "userAgent": s["user_agent"], "ip": s["ip"], "created": s["created"],
        "lastSeen": s["last_seen"], "expiresAt": s["expires_at"], "current": s["token_hash"] == current_hash,
    } for s in rows])


@bp.delete("/api/profile/sessions")
@login_required
def sessions_revoke():
    user = current_user()
    allowed, retry = _limit("sessions-revoke", 20, 600)
    if not allowed:
        return limited_response(retry)
    token = request.cookies.get(auth.SESSION_COOKIE)
    if request.args.get("all") == "others":
        if not token:
            return fail("Keine aktive Sitzung.", 401)
        cur = db.run("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], security.sha256(token)))
        return ok({"revoked": cur.rowcount})
    session_id = request.args.get("id")
    if not session_id:
        return fail("Sitzungs-ID fehlt.")
    cur = db.run("DELETE FROM sessions WHERE id=? AND user_id=?", (session_id, user["id"]))
    return ok() if cur.rowcount else fail("Sitzung nicht gefunden.", 404)
