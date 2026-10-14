"""Animem – Anime-Portal (Flask + SQLite). App-Factory."""
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth, db, langs, linkcheck, notify
from .config import build_config

MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{3,32})")
STAFF_OK_PREFIXES = ("/static/", "/api/health", "/login", "/logout", "/api/auth/")

CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; "
    "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; "
    "media-src 'self' blob: https:; frame-src https:; connect-src 'self'"
)


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(build_config())
    if overrides:
        app.config.update(overrides)
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_db(app.config["DB_PATH"])
    app.teardown_appcontext(db.close_db)

    # ---- Blueprints ------------------------------------------------------------------
    from .routes import (
        admin_pages, api_account, api_admin, api_auth, api_content, api_import, api_notify, api_social, api_streams,
        auth_pages, pages,
    )
    for module in (pages, auth_pages, admin_pages, api_auth, api_content, api_social, api_account, api_admin,
                   api_streams, api_import, api_notify):
        app.register_blueprint(module.bp)

    if app.config["LINKCHECK_INTERVAL_HOURS"] > 0 and not app.config.get("TESTING") and not app.config.get("NO_BACKGROUND"):
        linkcheck.scheduler(app, app.config["LINKCHECK_INTERVAL_HOURS"])

    # ---- Request-Hooks ---------------------------------------------------------------
    @app.before_request
    def guard():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin")
            if origin and urlparse(origin).netloc != request.host:
                return _error("Ungültige Herkunft der Anfrage.", 403)
            if not origin and request.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
                return _error("Ungültige Herkunft der Anfrage.", 403)
        if not request.path.startswith(STAFF_OK_PREFIXES) and db.get_setting("maintenance_mode", False):
            user = auth.current_user()
            if not (user and auth.can.manage_content(user["role"])):
                if request.path.startswith("/api/"):
                    return jsonify(error="Wartungsarbeiten – bitte später erneut versuchen."), 503
                return render_template("maintenance.html"), 503

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy", CSP)
        if request.is_secure:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.path.startswith("/api/") and "Cache-Control" not in resp.headers:
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---- Fehlerseiten ----------------------------------------------------------------
    def _error(message, status):
        if request.path.startswith("/api/"):
            return jsonify(error=message), status
        return render_template("error.html", status=status, message=message), status

    @app.errorhandler(404)
    def not_found(_e):
        return _error("Diese Seite gibt es nicht.", 404)

    @app.errorhandler(413)
    def too_large(_e):
        return _error("Datei ist zu groß.", 413)

    @app.errorhandler(405)
    def not_allowed(_e):
        return _error("Methode nicht erlaubt.", 405)

    @app.errorhandler(500)
    def server_error(_e):
        return _error("Auf dem Server ist ein Fehler aufgetreten.", 500)

    # ---- Templates -------------------------------------------------------------------
    @app.context_processor
    def inject():
        user = auth.current_user()
        counts = {"watchlist": 0, "subscriptions": 0, "notifications": 0}
        if user:
            counts["watchlist"] = db.scalar("SELECT COUNT(*) FROM watchlist_items WHERE user_id=?", (user["id"],))
            counts["subscriptions"] = db.scalar("SELECT COUNT(*) FROM subscriptions WHERE user_id=?", (user["id"],))
            counts["notifications"] = notify.unread_count(user["id"])
        return {
            "user": user, "can": auth.can, "ROLE_LABELS": auth.ROLE_LABELS, "counts": counts, "LANGS": langs.LANGS,
            "LANG_ORDER": langs.ORDER,
            "site_name": db.get_setting("site_name", "Animem"),
        }

    @app.template_filter("date_de")
    def date_de(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y")
        except ValueError:
            return ""

    @app.template_filter("datetime_de")
    def datetime_de(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return ""

    @app.template_filter("mentions")
    def mentions(text):
        safe = str(escape(text or ""))
        safe = MENTION_RE.sub(lambda m: f'<a class="mention" href="/u/{m.group(1)}">@{m.group(1)}</a>', safe)
        return Markup(safe)

    @app.template_filter("tojson_attr")
    def tojson_attr(value):
        import json
        return Markup(escape(json.dumps(value, ensure_ascii=False)))

    return app
