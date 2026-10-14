"""Automatischer Link-Check für Streams (ohne Zusatzpakete).

Bewertung einer URL:
  OK       erreichbar, kein Hinweis auf eine gelöschte Datei
  UNKNOWN  Anbieter blockt Automaten (401/403/429/503) – kein Urteil möglich
  FAIL     Fehler beim Abruf (nicht erreichbar, Timeout, 404/410, 5xx, "Datei gelöscht"-Seite)
Ein Link gilt erst nach 2 Fehlschlägen in Folge als DEAD (vorher SUSPECT), damit kurze Ausfälle nicht sofort auffallen.
"""
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import db

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
SOFT_404 = re.compile(
    r"(file (was )?not found|video (was )?not found|has been (deleted|removed)|no longer (available|exists)|"
    r"this video (is )?(unavailable|removed)|datei (existiert nicht|nicht gefunden|wurde gelöscht)|"
    r"video (nicht gefunden|wurde gelöscht)|removed due to|content (is )?not available|deleted by)", re.I)
BLOCKED = {401, 403, 429, 503}
STATE_KEY = "linkcheck_state"
STALE_AFTER = 2 * 3600  # ein "läuft"-Eintrag älter als 2 h gilt als abgestürzt


def default_fetch(url, timeout=10):
    """Gibt (http_code, text_anfang) zurück oder wirft eine Exception bei Verbindungsproblemen."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "de,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(60000).decode("utf-8", "ignore")
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""


FETCH = default_fetch  # in Tests austauschbar


def check_url(url, fetch=None):
    fetch = fetch or FETCH
    try:
        code, body = fetch(url)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
        return {"status": "FAIL", "code": None, "note": f"nicht erreichbar ({type(exc).__name__})"}
    except Exception as exc:  # unerwartetes Format o. Ä. -> nicht als "tot" werten
        return {"status": "UNKNOWN", "code": None, "note": f"Prüfung fehlgeschlagen ({type(exc).__name__})"}
    if code in BLOCKED:
        return {"status": "UNKNOWN", "code": code, "note": "Anbieter blockiert automatische Prüfung"}
    if code in (404, 410):
        return {"status": "FAIL", "code": code, "note": f"HTTP {code} – Datei nicht gefunden"}
    if code >= 500:
        return {"status": "FAIL", "code": code, "note": f"HTTP {code} – Serverfehler"}
    if code >= 400:
        return {"status": "FAIL", "code": code, "note": f"HTTP {code}"}
    if body and SOFT_404.search(body):
        return {"status": "FAIL", "code": code, "note": "Seite meldet: Datei gelöscht/nicht gefunden"}
    return {"status": "OK", "code": code, "note": ""}


def record(conn, url, result):
    """Speichert das Ergebnis und führt den Fehlerzähler (2 Fehlschläge in Folge = DEAD)."""
    old = conn.execute("SELECT * FROM stream_checks WHERE url=?", (url,)).fetchone()
    now = db.utcnow()
    fail_count = old["fail_count"] if old else 0
    last_ok = old["last_ok_at"] if old else ""
    if result["status"] == "OK":
        status, fail_count, last_ok = "OK", 0, now
    elif result["status"] == "FAIL":
        fail_count += 1
        status = "DEAD" if fail_count >= 2 else "SUSPECT"
    else:  # UNKNOWN: Zustand beibehalten
        status = old["status"] if old and old["status"] in ("OK", "SUSPECT", "DEAD") else "UNKNOWN"
    conn.execute(
        "INSERT INTO stream_checks (url, status, http_code, note, fail_count, checked_at, last_ok_at) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(url) DO UPDATE SET status=excluded.status, http_code=excluded.http_code, note=excluded.note, "
        "fail_count=excluded.fail_count, checked_at=excluded.checked_at, last_ok_at=excluded.last_ok_at",
        (url, status, result["code"], result["note"], fail_count, now, last_ok))
    return status


def collect_urls(conn):
    """Alle Stream-URLs veröffentlichter Folgen/Filme (geprüft wird nur, was Nutzer wirklich sehen)."""
    queries = (
        "SELECT e.streams FROM episodes e JOIN seasons se ON se.id = e.season_id JOIN series s ON s.id = se.series_id "
        "WHERE e.status = 'PUBLISHED' AND s.status = 'PUBLISHED'",
        "SELECT streams FROM movies WHERE status = 'PUBLISHED'",
    )
    urls = set()
    for sql in queries:
        for r in conn.execute(sql).fetchall():
            try:
                for st in json.loads(r["streams"] or "[]"):
                    if st.get("url"):
                        urls.add(st["url"])
            except ValueError:
                pass
    return urls


# ---- Laufzeit-Status (in der DB, damit mehrere Worker dasselbe sehen) --------------------------

def get_state(conn):
    r = conn.execute("SELECT value FROM app_settings WHERE key=?", (STATE_KEY,)).fetchone()
    try:
        return json.loads(r["value"]) if r else {}
    except ValueError:
        return {}


def set_state(conn, state):
    conn.execute("INSERT INTO app_settings (key, value, updated) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                 (STATE_KEY, json.dumps(state), db.utcnow()))


def claim(conn):
    """Sichert sich den Lauf (verhindert doppelte Läufe bei mehreren Workern/Klicks). True = Lauf darf starten."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        st = get_state(conn)
        if st.get("running") and time.time() - st.get("started_ts", 0) < STALE_AFTER:
            conn.execute("ROLLBACK")
            return False
        set_state(conn, {"running": True, "started": db.utcnow(), "started_ts": time.time(), "total": 0, "done": 0,
                         "dead": 0, "finished": st.get("finished", "")})
        conn.execute("COMMIT")
        return True
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def run_all(db_path, fetch=None, workers=4, pause=0.15):
    """Prüft alle Stream-URLs. Eigene DB-Verbindungen, daher auch aus Threads/CLI nutzbar. Setzt vorheriges claim() voraus."""
    conn = db._connect(db_path)
    try:
        urls = sorted(collect_urls(conn))
        st = get_state(conn); st.update(total=len(urls), done=0, dead=0); set_state(conn, st)

        def work(url):
            time.sleep(pause)  # Anbieter nicht fluten
            return url, check_url(url, fetch)

        done = dead = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for url, res in pool.map(work, urls):
                status = record(conn, url, res)
                done += 1
                dead += status == "DEAD"
                if done % 5 == 0 or done == len(urls):
                    st.update(done=done, dead=dead); set_state(conn, st)
        # Einträge für URLs, die es nicht mehr gibt, aufräumen
        if urls:
            marks = ",".join("?" for _ in urls)
            conn.execute(f"DELETE FROM stream_checks WHERE url NOT IN ({marks})", urls)
        st.update(running=False, finished=db.utcnow(), done=len(urls), dead=dead)
        set_state(conn, st)
        return {"total": len(urls), "dead": dead}
    except BaseException:
        st = get_state(conn); st.update(running=False); set_state(conn, st)
        raise
    finally:
        conn.close()


def start_background(db_path, fetch=None):
    """Startet einen Lauf im Hintergrund. False, wenn bereits einer läuft."""
    conn = db._connect(db_path)
    try:
        if not claim(conn):
            return False
    finally:
        conn.close()
    threading.Thread(target=lambda: run_all(db_path, fetch), name="linkcheck", daemon=True).start()
    return True


def scheduler(app, interval_hours):
    """Läuft als Daemon-Thread: prüft alle `interval_hours` Stunden automatisch (nur ein Worker gewinnt per claim)."""
    def loop():
        time.sleep(90)  # Start nicht ausbremsen
        while True:
            try:
                conn = db._connect(app.config["DB_PATH"])
                try:
                    st = get_state(conn)
                finally:
                    conn.close()
                finished = st.get("finished") or ""
                due = True
                if finished:
                    try:
                        from datetime import datetime
                        age = time.time() - datetime.fromisoformat(finished.replace("Z", "+00:00")).timestamp()
                        due = age >= interval_hours * 3600
                    except ValueError:
                        due = True
                if due:
                    start_background(app.config["DB_PATH"])
            except Exception:
                app.logger.exception("Link-Check-Scheduler")
            time.sleep(900)
    threading.Thread(target=loop, name="linkcheck-scheduler", daemon=True).start()
