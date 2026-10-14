"""Streams für den Player aufbereiten und Meldungen defekter Streams verwalten."""
from . import db
from .langs import LANGS, ordered, short

REPORT_FLAG_AT = 2  # ab so vielen Meldungen wird ein Stream im Player als "gemeldet" markiert


def _raw_streams(record):
    streams = record.get("streams") or []
    if streams:
        return [{"label": s.get("label", ""), "url": s.get("url", ""), "lang": s.get("lang", "")} for s in streams]
    if record.get("embed_url"):
        return [{"label": record.get("embed_provider", ""), "url": record["embed_url"], "lang": "OMU"}]
    return []


def player_streams(record, target_type, pref_lang=""):
    """Streams für den Player: Sprache, Zustand (Link-Check/Meldungen) und sinnvolle Reihenfolge.

    Reihenfolge: funktionierende vor (vermutlich) toten; darin zuerst die bevorzugte Sprache, sonst Eingabe-Reihenfolge.
    """
    raw = _raw_streams(record)
    if not raw:
        return []
    urls = [s["url"] for s in raw]
    marks = ",".join("?" for _ in urls)
    checks = {r["url"]: r for r in db.rows(f"SELECT url, status FROM stream_checks WHERE url IN ({marks})", urls)}
    reports = {r["url"]: r["count"] for r in db.rows(
        "SELECT url, count FROM stream_reports WHERE target_type=? AND target_id=? AND status='OPEN'", (target_type, record["id"]))}
    out = []
    for i, s in enumerate(raw):
        status = checks.get(s["url"], {}).get("status", "")
        n = reports.get(s["url"], 0)
        out.append({**s, "lang_short": short(s["lang"]), "lang_name": LANGS.get(s["lang"], {}).get("name", ""),
                    "dead": status == "DEAD", "reported": n >= REPORT_FLAG_AT, "order": i})
    out.sort(key=lambda s: (s["dead"] or s["reported"], 0 if (pref_lang and s["lang"] == pref_lang) else 1, s["order"]))
    for i, s in enumerate(out):
        s["index"] = i
    return out


def languages_of(streams):
    return ordered({s["lang"] for s in streams if s["lang"]})


def default_language(streams, pref_lang):
    """Welche Sprache soll vorausgewählt sein? Die bevorzugte, wenn dort ein funktionierender Stream existiert."""
    if pref_lang and any(s["lang"] == pref_lang and not s["dead"] for s in streams):
        return pref_lang
    return ""


# ---- Meldungen -----------------------------------------------------------------------------

def target_record(target_type, target_id):
    return db.get("episodes" if target_type == "EPISODE" else "movies", target_id)


def report_stream(target_type, target_id, url, user_id=None):
    """Meldet einen Stream. Gibt (Status, Zähler) zurück: 'new' | 'counted' | 'ignored' | 'missing'."""
    rec = target_record(target_type, target_id)
    if not rec:
        return "missing", 0
    stream = next((s for s in _raw_streams(rec) if s["url"] == url), None)
    if not stream:
        return "missing", 0
    existing = db.row("SELECT * FROM stream_reports WHERE target_type=? AND target_id=? AND url=? AND status IN ('OPEN','IGNORED') "
                      "ORDER BY created DESC", (target_type, target_id, url))
    if existing and existing["status"] == "IGNORED":
        return "ignored", existing["count"]
    if existing:
        db.update("stream_reports", existing["id"], {"count": existing["count"] + 1})
        return "counted", existing["count"] + 1
    db.insert("stream_reports", {"target_type": target_type, "target_id": target_id, "url": url, "label": stream["label"],
                                 "lang": stream["lang"], "count": 1, "status": "OPEN", "first_user_id": user_id})
    return "new", 1


def describe_target(target_type, target_id):
    """Menschenlesbare Beschreibung + Admin-Link für die Meldungsliste."""
    if target_type == "MOVIE":
        m = db.get("movies", target_id)
        return ({"title": m["title"], "where": "Film", "edit": f"/admin/movies/{m['id']}/edit", "view": f"/movies/{m['slug']}"} if m else None)
    r = db.row("SELECT e.number AS en, e.title AS et, se.number AS sn, s.id AS sid, s.title AS st, s.slug FROM episodes e "
               "JOIN seasons se ON se.id=e.season_id JOIN series s ON s.id=se.series_id WHERE e.id=?", (target_id,))
    if not r:
        return None
    return {"title": r["st"], "where": f"Staffel {r['sn']} · Folge {r['en']} – {r['et']}", "edit": f"/admin/series/{r['sid']}/edit",
            "view": f"/series/{r['slug']}/s/{r['sn']}/e/{r['en']}"}


def close_stale_reports(target_type, target_id, current_urls, note="Link wurde ersetzt/entfernt"):
    """Offene Meldungen, deren URL nicht mehr zum Ziel gehört (Admin hat sie ersetzt/entfernt), als behoben schließen."""
    for r in db.rows("SELECT id, url FROM stream_reports WHERE target_type=? AND target_id=? AND status='OPEN'", (target_type, target_id)):
        if r["url"] not in current_urls:
            db.update("stream_reports", r["id"], {"status": "FIXED", "note": note})


def remove_stream(target_type, target_id, url):
    """Entfernt einen Stream aus Folge/Film. Gibt True zurück, wenn etwas entfernt wurde."""
    table = "episodes" if target_type == "EPISODE" else "movies"
    rec = db.get(table, target_id)
    if not rec:
        return False
    streams = [s for s in (rec["streams"] or []) if s.get("url") != url]
    if len(streams) == len(rec["streams"] or []):
        return False
    first = streams[0] if streams else None
    data = {"streams": streams, "embed_url": first["url"] if first else "", "embed_provider": first["label"] if first else ""}
    if target_type == "EPISODE" and not streams:
        data["status"] = "DRAFT"  # ohne Stream nicht mehr abrufbar
    db.update(table, target_id, data)
    close_stale_reports(target_type, target_id, {s["url"] for s in streams})
    return True
