"""Sessions, aktueller Nutzer, Rollen & Rechte."""
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, url_for

from . import db
from .security import fail, new_token, sha256, client_ip

SESSION_COOKIE = "animem_session"
SESSION_TTL = 14 * 86400
PENDING_TTL = 10 * 60

# ---- Rollen --------------------------------------------------------------------------

ROLE_RANK = {"USER": 0, "ADMIN": 1, "HEAD_ADMIN": 2, "OWNER": 3}
ROLE_LABELS = {"OWNER": "Owner", "HEAD_ADMIN": "Head Admin", "ADMIN": "Admin", "USER": "User"}


def has_min_role(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[minimum]


class Can:
    manage_content = staticmethod(lambda role: has_min_role(role, "ADMIN"))
    manage_admins = staticmethod(lambda role: has_min_role(role, "HEAD_ADMIN"))
    assign_roles = staticmethod(lambda role: has_min_role(role, "OWNER"))
    moderate = staticmethod(lambda role: has_min_role(role, "ADMIN"))
    manage_settings = staticmethod(lambda role: has_min_role(role, "OWNER"))


can = Can()


def assignable_roles(actor_role: str) -> list[str]:
    if actor_role == "OWNER":
        return ["USER", "ADMIN", "HEAD_ADMIN"]
    if actor_role == "HEAD_ADMIN":
        return ["USER", "ADMIN"]
    return []


def can_manage_target_role(actor_role: str, target_role: str) -> bool:
    if actor_role == "OWNER":
        return True
    if actor_role == "HEAD_ADMIN":
        return target_role in ("USER", "ADMIN")
    return False


# ---- Sessions ------------------------------------------------------------------------

def create_session(user_id: str, pending: bool = False) -> str:
    token = new_token()
    now = db.utcnow()
    db.insert("sessions", {
        "user_id": user_id,
        "token_hash": sha256(token),
        "expires_at": db.iso_in(PENDING_TTL if pending else SESSION_TTL),
        "pending_2fa": pending,
        "user_agent": (request.headers.get("User-Agent") or "")[:300] or None,
        "ip": client_ip(),
        "last_seen": now,
        "created": now,
    })
    return token


def confirm_pending_session(token: str):
    db.run(
        "UPDATE sessions SET pending_2fa=0, expires_at=? WHERE token_hash=?",
        (db.iso_in(SESSION_TTL), sha256(token)),
    )


def delete_session(token: str):
    db.run("DELETE FROM sessions WHERE token_hash=?", (sha256(token),))


def set_session_cookie(resp, token: str, pending: bool = False):
    resp.set_cookie(
        SESSION_COOKIE, token,
        max_age=PENDING_TTL if pending else SESSION_TTL,
        httponly=True, samesite="Lax", path="/", secure=request.is_secure,
    )
    return resp


def clear_session_cookie(resp):
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


def _owner_identity_ok(record: dict) -> bool:
    cfg = current_app.config
    emails, names = cfg["OWNER_EMAILS"], cfg["OWNER_USERNAMES"]
    if not emails and not names:
        return False  # OWNER ohne konfigurierte Identität gilt nicht als eingeloggt
    email_ok = not emails or record["email"].lower() in emails
    name_ok = not names or record["username"] in names
    return email_ok and name_ok


def current_user():
    """Eingeloggter Nutzer (dict) oder None. Pro Request gecacht."""
    if "current_user" in g:
        return g.current_user
    g.current_user = None
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    th = sha256(token)
    record = db.row(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash=? AND s.pending_2fa=0 AND s.expires_at > ? LIMIT 1",
        (th, db.utcnow()),
    )
    if not record or record["is_banned"]:
        return None
    if record["role"] == "OWNER" and not _owner_identity_ok(record):
        return None
    # Aktivitäts-Heartbeat (höchstens alle 5 Minuten schreiben)
    db.run("UPDATE sessions SET last_seen=? WHERE token_hash=? AND last_seen < ?", (db.utcnow(), th, db.iso_ago(300)))
    g.current_user = {
        "id": record["id"],
        "username": record["username"],
        "email": record["email"],
        "role": record["role"],
        "avatar_url": record["avatar_url"] or None,
        "two_factor_enabled": bool(record["totp_enabled"]),
    }
    return g.current_user


# ---- Decorators ----------------------------------------------------------------------

def _wants_json() -> bool:
    return request.path.startswith("/api/")


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            if _wants_json():
                return fail("Nicht angemeldet", 401)
            return redirect(url_for("auth_pages.login", next=request.full_path.rstrip("?")))
        return fn(*a, **kw)
    return wrapper


def role_required(check, redirect_to="pages.home"):
    """check: Callable(role) -> bool, z.B. can.manage_content."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if not user or not check(user["role"]):
                if _wants_json():
                    return fail("Nicht berechtigt", 403)
                return redirect(url_for(redirect_to))
            return fn(*a, **kw)
        return wrapper
    return deco


def owner_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        user = current_user()
        if not user or user["role"] != "OWNER":
            if _wants_json():
                return fail("Nicht berechtigt", 403)
            return redirect(url_for("pages.home"))
        return fn(*a, **kw)
    return wrapper
