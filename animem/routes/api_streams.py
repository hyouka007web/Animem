"""/api/streams/report (öffentlich) und Admin-Aktionen für Meldungen und Link-Check."""
import hashlib

from flask import Blueprint, current_app, request

from .. import db, linkcheck, security, services, streamtools
from ..auth import can, current_user, role_required
from ..security import fail, limited_response, ok

bp = Blueprint("api_streams", __name__)


@bp.post("/api/streams/report")
def report():
    """Meldet einen nicht funktionierenden Stream. Auch ohne Konto möglich (Rate-Limit pro IP)."""
    allowed, retry = security.rate_limit("stream-report", 12, 600)
    if not allowed:
        return limited_response(retry)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail("Ungültige Anfrage.")
    target_type, target_id, url = data.get("targetType"), data.get("targetId"), data.get("url")
    if target_type not in ("EPISODE", "MOVIE") or not isinstance(target_id, str) or not isinstance(url, str) or len(url) > 2000:
        return fail("Ungültige Meldung.")
    # Dieselbe Person (IP) darf denselben Stream nur einmal pro Stunde melden, damit Zähler nicht manipulierbar sind.
    key = hashlib.sha1(f"{target_id}|{url}".encode()).hexdigest()[:20]
    first_time, _ = security.rate_limit("stream-report-dup", 1, 3600, key=f"{security.client_ip()}:{key}")
    user = current_user()
    if not first_time:
        return ok({"success": True, "already": True})
    status, count = streamtools.report_stream(target_type, target_id, url, user["id"] if user else None)
    if status == "missing":
        return fail("Dieser Stream existiert nicht (mehr).", 404)
    return ok({"success": True, "status": status, "count": count})


# ---- Admin ---------------------------------------------------------------------------------

@bp.post("/api/admin/streams/check")
@role_required(can.moderate)
def check_one():
    """Prüft eine einzelne URL sofort (z. B. aus der Meldungsliste)."""
    data = request.get_json(silent=True)
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2000:
        return fail("Ungültige URL.")
    res = linkcheck.check_url(url)
    conn = db.get_db()
    status = linkcheck.record(conn, url, res)
    return ok({"status": status, "note": res["note"], "code": res["code"]})


@bp.post("/api/admin/streams/check-all")
@role_required(can.moderate)
def check_all():
    started = linkcheck.start_background(current_app.config["DB_PATH"])
    return ok({"started": started})


@bp.get("/api/admin/streams/check-status")
@role_required(can.moderate)
def check_status():
    st = linkcheck.get_state(db.get_db())
    return ok({k: st.get(k) for k in ("running", "started", "finished", "total", "done", "dead")})


@bp.patch("/api/admin/reports/<report_id>")
@role_required(can.moderate)
def update_report(report_id):
    data = request.get_json(silent=True)
    action = data.get("action") if isinstance(data, dict) else None
    rep = db.get("stream_reports", report_id)
    if not rep:
        return fail("Meldung nicht gefunden.", 404)
    user = current_user()
    if action == "resolve":
        db.update("stream_reports", report_id, {"status": "FIXED", "note": "Als behoben markiert"})
    elif action == "ignore":
        db.update("stream_reports", report_id, {"status": "IGNORED", "note": "Ignoriert"})
    elif action == "reopen":
        db.update("stream_reports", report_id, {"status": "OPEN", "note": ""})
    elif action == "remove_stream":
        if not streamtools.remove_stream(rep["target_type"], rep["target_id"], rep["url"]):
            db.update("stream_reports", report_id, {"status": "FIXED", "note": "Stream war schon entfernt"})
        services.audit(user["id"], "STREAM_REMOVED", rep["target_type"], rep["target_id"], {"url": rep["url"]})
    else:
        return fail("Unbekannte Aktion.")
    return ok({"success": True})
