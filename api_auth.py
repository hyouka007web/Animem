"""/api/auth/* – Anmeldung, Registrierung, 2FA-Bestätigung, Abmeldung."""
import sqlite3

from flask import Blueprint, redirect, request

from .. import auth, db, security, validation
from ..security import fail, limited_response, ok

bp = Blueprint("api_auth", __name__)

BAD_LOGIN = "E-Mail oder Passwort ist falsch."


def _payload() -> tuple[dict, bool]:
    """Liefert (Daten, ist_formular). Formulare werden mit Redirects beantwortet."""
    if request.is_json:
        return (request.get_json(silent=True) or {}), False
    return request.form.to_dict(), True


def _safe_next(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _form_error(page: str, message: str, nxt: str | None = None):
    from urllib.parse import urlencode
    qs = {"error": message}
    if nxt:
        qs["next"] = nxt
    return redirect(f"/{page}?{urlencode(qs)}", 303)


def _drop_old_session():
    old = request.cookies.get(auth.SESSION_COOKIE)
    if old:
        auth.delete_session(old)  # Session-Fixation vermeiden


@bp.post("/api/auth/login")
def login():
    allowed, retry = security.rate_limit("auth-login", 8, 15 * 60)
    if not allowed:
        return limited_response(retry)
    data, is_form = _payload()
    nxt = _safe_next(data.get("next")) if is_form else "/"
    email = str(data.get("email") or "").strip()
    password = data.get("password")
    if not email or not isinstance(password, str) or not password or len(email) > 254 or len(password) > 128:
        return _form_error("login", BAD_LOGIN, nxt) if is_form else fail(BAD_LOGIN, 401)

    record = db.row("SELECT * FROM users WHERE email=? LIMIT 1", (email,))
    valid = security.verify_password(password, record["password_hash"] if record else None)
    if not record or not valid or record["is_banned"]:
        return _form_error("login", BAD_LOGIN, nxt) if is_form else fail(BAD_LOGIN, 401)

    _drop_old_session()
    if record["totp_enabled"]:
        token = auth.create_session(record["id"], pending=True)
        resp = redirect(f"/login?step=totp&next={nxt}", 303) if is_form else ok({"requiresTotp": True})
        return auth.set_session_cookie(resp, token, pending=True)

    token = auth.create_session(record["id"])
    resp = redirect(nxt, 303) if is_form else ok(
        {"user": {"id": record["id"], "username": record["username"], "role": record["role"]}}
    )
    return auth.set_session_cookie(resp, token)


@bp.post("/api/auth/register")
def register():
    allowed, retry = security.rate_limit("auth-register", 5, 15 * 60)
    if not allowed:
        return limited_response(retry)
    data, is_form = _payload()

    def error(message, status=400):
        return _form_error("register", message) if is_form else fail(message, status)

    if not db.get_setting("registration_open", True):
        return error("Die Registrierung ist derzeit geschlossen.", 403)
    try:
        v = validation.registration(data)
    except validation.ValidationError as exc:
        return error(str(exc))
    try:
        with db.transaction():
            record = db.insert("users", {
                "email": v["email"], "username": v["username"], "password_hash": security.hash_password(v["password"]),
                "role": "USER",
            })
    except sqlite3.IntegrityError:
        return error("E-Mail oder Benutzername wird bereits verwendet.")

    _drop_old_session()
    token = auth.create_session(record["id"])
    resp = redirect("/", 303) if is_form else ok({"user": {"id": record["id"], "username": record["username"], "role": "USER"}}, 201)
    return auth.set_session_cookie(resp, token)


@bp.post("/api/auth/totp")
def totp_login():
    pending = request.cookies.get(auth.SESSION_COOKIE)
    data, is_form = _payload()
    nxt = _safe_next(data.get("next")) if is_form else "/"

    def error(message, status=401):
        if is_form:
            from urllib.parse import urlencode
            return redirect("/login?" + urlencode({"step": "totp", "error": message, "next": nxt}), 303)
        return fail(message, status)

    if not pending:
        return error("Keine ausstehende Anmeldung gefunden.")
    allowed, retry = security.rate_limit("auth-totp", 10, 10 * 60, key=pending[:16])
    if not allowed:
        return limited_response(retry)
    code = str(data.get("code") or "").strip()
    if not 6 <= len(code) <= 64:
        return error("Ungültiger Code.", 400)

    record = db.row(
        "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
        "WHERE s.token_hash=? AND s.pending_2fa=1 AND s.expires_at > ? LIMIT 1",
        (security.sha256(pending), db.utcnow()),
    )
    if not record or record["is_banned"]:
        return error("Anmeldevorgang abgelaufen. Bitte erneut anmelden.")

    used_recovery = False
    if not (record["totp_secret"] and security.verify_totp(record["totp_secret"], code)):
        hashed = security.sha256(code.lower())
        codes = record["totp_recovery_codes"] if isinstance(record["totp_recovery_codes"], list) else []
        remaining = [c for c in codes if c != hashed]
        if len(remaining) == len(codes):
            return error("Der Code ist ungültig oder abgelaufen.")
        used_recovery = True
        db.update("users", record["id"], {"totp_recovery_codes": remaining})

    auth.confirm_pending_session(pending)
    resp = redirect(nxt, 303) if is_form else ok({
        "user": {"id": record["id"], "username": record["username"], "role": record["role"]},
        "usedRecoveryCode": used_recovery,
    })
    return auth.set_session_cookie(resp, pending)


@bp.delete("/api/auth/session")
def logout_api():
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.delete_session(token)
    return auth.clear_session_cookie(ok())


@bp.post("/logout")
def logout_form():
    token = request.cookies.get(auth.SESSION_COOKIE)
    if token:
        auth.delete_session(token)
    return auth.clear_session_cookie(redirect("/", 303))
