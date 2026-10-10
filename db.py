"""Dünne SQLite-Schicht: eine Verbindung pro Request, dict-Zeilen, JSON/Bool-Konvertierung."""
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g

JSON_COLS = {"genre_ids", "tag_ids", "streams", "metadata", "totp_recovery_codes"}
BOOL_COLS = {
    "is_banned", "totp_enabled", "pending_2fa", "is_pinned", "is_locked",
    "completed", "is_staff", "is_read", "notify_on_new_episode",
}
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

DEFAULT_FORUM_CATEGORIES = [
    ("Allgemein", "allgemein", "Alles rund um Animem und Anime im Allgemeinen."),
    ("Anime-Talk", "anime-talk", "Diskussionen zu Serien, Filmen und Staffeln."),
    ("Empfehlungen", "empfehlungen", "Tipps und Wünsche für neue Titel."),
    ("Hilfe & Feedback", "hilfe-feedback", "Fragen, Fehler und Verbesserungsvorschläge."),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def iso_in(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def iso_ago(seconds: float) -> str:
    return iso_in(-seconds)


def new_id() -> str:
    return uuid.uuid4().hex


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.DatabaseError:
        pass  # manche Dateisysteme (z.B. /sdcard) können kein WAL – dann eben Standardmodus
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = _connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k, v in d.items():
        if k in JSON_COLS and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except ValueError:
                pass
        elif k in BOOL_COLS and v is not None:
            d[k] = bool(v)
    return d


def rows(sql, args=()):
    return [_row(r) for r in get_db().execute(sql, args).fetchall()]


def row(sql, args=()):
    return _row(get_db().execute(sql, args).fetchone())


def scalar(sql, args=()):
    r = get_db().execute(sql, args).fetchone()
    return r[0] if r else None


def run(sql, args=()):
    return get_db().execute(sql, args)


def _prep(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _ident(name):
    if not _IDENT.match(name):
        raise ValueError(f"Ungültiger Bezeichner: {name!r}")
    return name


_COLUMN_CACHE: dict[str, set[str]] = {}


def _columns(table: str) -> set[str]:
    if table not in _COLUMN_CACHE:
        _COLUMN_CACHE[table] = {r["name"] for r in get_db().execute(f'PRAGMA table_info("{_ident(table)}")').fetchall()}
    return _COLUMN_CACHE[table]


def insert(table, data):
    payload = dict(data)
    payload.setdefault("id", new_id())
    columns = _columns(table)
    if "created" in columns:
        payload.setdefault("created", utcnow())
    if "updated" in columns:
        payload.setdefault("updated", payload.get("created") or utcnow())
    cols = [_ident(c) for c in payload]
    quoted = ", ".join(f'"{c}"' for c in cols)
    marks = ", ".join("?" for _ in cols)
    get_db().execute(f'INSERT INTO "{_ident(table)}" ({quoted}) VALUES ({marks})', [_prep(payload[c]) for c in cols])
    return row(f'SELECT * FROM "{table}" WHERE id=?', (payload["id"],))


def update(table, record_id, data, touch=True):
    payload = dict(data)
    if touch and "updated" in _columns(table):
        payload["updated"] = utcnow()
    if not payload:
        return row(f'SELECT * FROM "{_ident(table)}" WHERE id=?', (record_id,))
    cols = [_ident(c) for c in payload]
    sets = ", ".join(f'"{c}"=?' for c in cols)
    cur = get_db().execute(
        f'UPDATE "{_ident(table)}" SET {sets} WHERE id=?', [_prep(payload[c]) for c in cols] + [record_id]
    )
    if cur.rowcount == 0:
        return None
    return row(f'SELECT * FROM "{table}" WHERE id=?', (record_id,))


def get(table, record_id):
    if not record_id:
        return None
    return row(f'SELECT * FROM "{_ident(table)}" WHERE id=?', (record_id,))


def delete(table, record_id):
    return get_db().execute(f'DELETE FROM "{_ident(table)}" WHERE id=?', (record_id,)).rowcount > 0


@contextmanager
def transaction():
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ---- Einstellungen -------------------------------------------------------------------

SETTING_DEFAULTS = {"site_name": "Animem", "registration_open": True, "maintenance_mode": False}


def get_setting(key, default=None):
    r = get_db().execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    if r is None:
        return SETTING_DEFAULTS.get(key, default)
    try:
        return json.loads(r["value"])
    except ValueError:
        return default


def all_settings():
    out = dict(SETTING_DEFAULTS)
    for r in get_db().execute("SELECT key, value FROM app_settings").fetchall():
        try:
            out[r["key"]] = json.loads(r["value"])
        except ValueError:
            pass
    return out


def set_setting(key, value):
    get_db().execute(
        "INSERT INTO app_settings (key, value, updated) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
        (key, json.dumps(value), utcnow()),
    )


# ---- Initialisierung -----------------------------------------------------------------

def init_db(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        if conn.execute("SELECT COUNT(*) FROM forum_categories").fetchone()[0] == 0:
            now = utcnow()
            for i, (name, slug, desc) in enumerate(DEFAULT_FORUM_CATEGORIES):
                conn.execute(
                    'INSERT INTO forum_categories (id, name, slug, description, "order", created, updated) VALUES (?,?,?,?,?,?,?)',
                    (new_id(), name, slug, desc, i, now, now),
                )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utcnow(),))
    finally:
        conn.close()
