"""Seiten für Anmeldung und Registrierung."""
from flask import Blueprint, redirect, render_template, request

from .. import auth, db, security
from ..auth import current_user

bp = Blueprint("auth_pages", __name__)


def _safe_next(value):
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _has_pending_session() -> bool:
    token = request.cookies.get(auth.SESSION_COOKIE)
    if not token:
        return False
    return bool(db.row("SELECT 1 AS x FROM sessions WHERE token_hash=? AND pending_2fa=1 AND expires_at > ?",
                       (security.sha256(token), db.utcnow())))


@bp.get("/login")
def login():
    nxt = _safe_next(request.args.get("next"))
    if current_user():
        return redirect(nxt)
    step = "totp" if request.args.get("step") == "totp" and _has_pending_session() else "password"
    return render_template("login.html", step=step, error=request.args.get("error"), next=nxt)


@bp.get("/register")
def register():
    if current_user():
        return redirect("/")
    return render_template("register.html", error=request.args.get("error"),
                           open=db.get_setting("registration_open", True))
