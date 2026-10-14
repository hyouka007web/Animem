"""Dünne SQLite-Schicht: eine Verbindung pro Request, dict-Zeilen, JSON/Bool-Konvertierung."""
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g

JSON_COLS = {"genre_ids", "tag_ids", "streams", "metadata", "totp_recovery_codes", "notify_langs", "alt_titles"}
BOOL_COLS = {
    "is_banned", "totp_enabled", "pending_2fa", "is_pinned", "is_locked",
    "completed", "is_staff", "is_read", "notify_on_new_episode", "notify_new_langs",
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

def _table_columns(conn, table):
    return {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _migrate(conn):
    """Bringt eine ältere Datenbank auf den aktuellen Stand (läuft VOR schema.sql, ist idempotent)."""
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # 1) Staffeln: eigenes Bild + Bewertungswerte
    if "seasons" in tables:
        cols = _table_columns(conn, "seasons")
        if "thumbnail_url" not in cols:
            conn.execute("ALTER TABLE seasons ADD COLUMN thumbnail_url TEXT NOT NULL DEFAULT ''")
        if "avg_rating" not in cols:
            conn.execute("ALTER TABLE seasons ADD COLUMN avg_rating REAL NOT NULL DEFAULT 0")
        if "ratings_count" not in cols:
            conn.execute("ALTER TABLE seasons ADD COLUMN ratings_count INTEGER NOT NULL DEFAULT 0")

    # 2) Bewertungen: Zieltyp SEASON + Spalte season_id (CHECK-Regel lässt sich in SQLite nur per Neuaufbau ändern)
    if "ratings" in tables and "season_id" not in _table_columns(conn, "ratings"):
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        try:
            conn.execute("ALTER TABLE ratings RENAME TO ratings_old")
            for idx in ("idx_ratings_user_series", "idx_ratings_user_movie", "idx_ratings_user_episode"):
                conn.execute(f"DROP INDEX IF EXISTS {idx}")
            conn.execute("""CREATE TABLE ratings (
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              target_type TEXT NOT NULL CHECK (target_type IN ('SERIES','SEASON','MOVIE','EPISODE')),
              series_id TEXT, season_id TEXT, movie_id TEXT, episode_id TEXT,
              value INTEGER NOT NULL CHECK (value BETWEEN 1 AND 10), comment TEXT NOT NULL DEFAULT '',
              created TEXT NOT NULL, updated TEXT NOT NULL)""")
            # Film- und Folgen-Bewertungen unverändert übernehmen
            conn.execute("""INSERT INTO ratings (id, user_id, target_type, series_id, season_id, movie_id, episode_id, value, comment, created, updated)
              SELECT id, user_id, target_type, NULL, NULL, movie_id, episode_id, value, comment, created, updated
              FROM ratings_old WHERE target_type IN ('MOVIE','EPISODE')""")
            # Alte Serien-Bewertungen zählen künftig für die erste Staffel der Serie
            conn.execute("""INSERT OR IGNORE INTO ratings (id, user_id, target_type, series_id, season_id, movie_id, episode_id, value, comment, created, updated)
              SELECT r.id, r.user_id, 'SEASON', NULL,
                     (SELECT s.id FROM seasons s WHERE s.series_id = r.series_id ORDER BY s.number LIMIT 1),
                     NULL, NULL, r.value, r.comment, r.created, r.updated
              FROM ratings_old r WHERE r.target_type = 'SERIES'
                AND EXISTS (SELECT 1 FROM seasons s WHERE s.series_id = r.series_id)""")
            conn.execute("DROP TABLE ratings_old")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")


ADD_COLUMNS = {
    "users": {"pref_lang": "TEXT NOT NULL DEFAULT ''",
              "notify_langs": "TEXT NOT NULL DEFAULT '[\"GERDUB\",\"GERSUB\",\"OMU\"]'",
              "notify_new_langs": "INTEGER NOT NULL DEFAULT 1"},
    "subscriptions": {"notify_langs": "TEXT"},
    "series": {"alt_titles": "TEXT NOT NULL DEFAULT '[]'", "year": "INTEGER", "air_status": "TEXT NOT NULL DEFAULT ''",
               "content_updated": "TEXT NOT NULL DEFAULT ''", "last_update_note": "TEXT NOT NULL DEFAULT ''"},
    "movies": {"alt_titles": "TEXT NOT NULL DEFAULT '[]'", "year": "INTEGER"},
    "episodes": {"aired_at": "TEXT NOT NULL DEFAULT ''"},
    "notifications": {"dedupe_key": "TEXT NOT NULL DEFAULT ''"},
}


def _migrate_columns(conn):
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for table, cols in ADD_COLUMNS.items():
        if table not in tables:
            continue
        have = _table_columns(conn, table)
        for name, ddl in cols.items():
            if name not in have:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')
    if "series" in tables:
        conn.execute("UPDATE series SET content_updated = created WHERE content_updated = ''")


def _migrate_stream_langs(conn):
    """Ältere Streams hatten keine Sprache -> als 'OMU' kennzeichnen (im Editor korrigierbar)."""
    for table in ("episodes", "movies"):
        for r in conn.execute(f'SELECT id, streams, embed_url, embed_provider FROM "{table}"').fetchall():
            try:
                streams = json.loads(r["streams"] or "[]")
            except ValueError:
                streams = []
            changed = False
            if not streams and r["embed_url"]:
                streams = [{"label": r["embed_provider"] or "Stream", "url": r["embed_url"], "lang": "OMU"}]
                changed = True
            for s in streams:
                if isinstance(s, dict) and not s.get("lang"):
                    s["lang"] = "OMU"
                    changed = True
            if changed:
                conn.execute(f'UPDATE "{table}" SET streams=? WHERE id=?', (json.dumps(streams, ensure_ascii=False), r["id"]))


def _recalc_all_ratings(conn):
    """Berechnet die gespeicherten Durchschnittswerte aller Staffeln/Serien/Filme aus den Bewertungen neu."""
    conn.execute("""UPDATE seasons SET
        avg_rating = COALESCE((SELECT ROUND(AVG(value), 1) FROM ratings WHERE target_type='SEASON' AND season_id = seasons.id), 0),
        ratings_count = (SELECT COUNT(*) FROM ratings WHERE target_type='SEASON' AND season_id = seasons.id)""")
    conn.execute("""UPDATE series SET
        avg_rating = COALESCE((SELECT ROUND(AVG(r.value), 1) FROM ratings r JOIN seasons s ON s.id = r.season_id
                               WHERE r.target_type='SEASON' AND s.series_id = series.id), 0),
        ratings_count = (SELECT COUNT(*) FROM ratings r JOIN seasons s ON s.id = r.season_id
                         WHERE r.target_type='SEASON' AND s.series_id = series.id)""")


def init_db(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        _migrate(conn)
        _migrate_columns(conn)
        conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        if conn.execute("SELECT COUNT(*) FROM forum_categories").fetchone()[0] == 0:
            now = utcnow()
            for i, (name, slug, desc) in enumerate(DEFAULT_FORUM_CATEGORIES):
                conn.execute(
                    'INSERT INTO forum_categories (id, name, slug, description, "order", created, updated) VALUES (?,?,?,?,?,?,?)',
                    (new_id(), name, slug, desc, i, now, now),
                )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utcnow(),))
        _migrate_stream_langs(conn)
        _recalc_all_ratings(conn)
    finally:
        conn.close()
