-- Animem (Python/Flask) – SQLite-Schema. Idempotent: darf bei jedem Start laufen.

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  role TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('USER','ADMIN','HEAD_ADMIN','OWNER')),
  display_name TEXT NOT NULL DEFAULT '',
  avatar_url TEXT NOT NULL DEFAULT '',
  banner_url TEXT NOT NULL DEFAULT '',
  bio TEXT NOT NULL DEFAULT '',
  is_banned INTEGER NOT NULL DEFAULT 0,
  totp_secret TEXT,
  totp_enabled INTEGER NOT NULL DEFAULT 0,
  totp_recovery_codes TEXT NOT NULL DEFAULT '[]',
  pref_lang TEXT NOT NULL DEFAULT '',
  notify_langs TEXT NOT NULL DEFAULT '["GERDUB","GERSUB","OMU"]',
  notify_new_langs INTEGER NOT NULL DEFAULT 1,
  created TEXT NOT NULL,
  updated TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_display_name ON users(display_name COLLATE NOCASE) WHERE display_name <> '';
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  pending_2fa INTEGER NOT NULL DEFAULT 0,
  user_agent TEXT,
  ip TEXT,
  last_seen TEXT NOT NULL,
  created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS uploads (
  id TEXT PRIMARY KEY,
  file TEXT NOT NULL,
  mime TEXT NOT NULL,
  size INTEGER NOT NULL,
  created TEXT NOT NULL,
  updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genres (id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tags   (id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, created TEXT NOT NULL, updated TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS series (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '', thumbnail_url TEXT NOT NULL, banner_url TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
  avg_rating REAL NOT NULL DEFAULT 0, ratings_count INTEGER NOT NULL DEFAULT 0, view_count INTEGER NOT NULL DEFAULT 0,
  created_by TEXT, genre_ids TEXT NOT NULL DEFAULT '[]', tag_ids TEXT NOT NULL DEFAULT '[]',
  alt_titles TEXT NOT NULL DEFAULT '[]', year INTEGER, air_status TEXT NOT NULL DEFAULT '',
  content_updated TEXT NOT NULL DEFAULT '', last_update_note TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_series_status ON series(status);
CREATE INDEX IF NOT EXISTS idx_series_created ON series(created DESC);

CREATE TABLE IF NOT EXISTS seasons (
  id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  number INTEGER NOT NULL, title TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL,
  thumbnail_url TEXT NOT NULL DEFAULT '', avg_rating REAL NOT NULL DEFAULT 0, ratings_count INTEGER NOT NULL DEFAULT 0,
  UNIQUE(series_id, number)
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY, season_id TEXT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
  number INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  embed_url TEXT NOT NULL, embed_provider TEXT NOT NULL DEFAULT '', streams TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED')), aired_at TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(season_id, number)
);
CREATE INDEX IF NOT EXISTS idx_episodes_season ON episodes(season_id, number);

CREATE TABLE IF NOT EXISTS movies (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
  thumbnail_url TEXT NOT NULL, banner_url TEXT NOT NULL DEFAULT '', embed_url TEXT NOT NULL,
  embed_provider TEXT NOT NULL DEFAULT '', streams TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED')),
  avg_rating REAL NOT NULL DEFAULT 0, ratings_count INTEGER NOT NULL DEFAULT 0, created_by TEXT,
  genre_ids TEXT NOT NULL DEFAULT '[]', tag_ids TEXT NOT NULL DEFAULT '[]',
  alt_titles TEXT NOT NULL DEFAULT '[]', year INTEGER,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(status);

CREATE TABLE IF NOT EXISTS ratings (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN ('SERIES','SEASON','MOVIE','EPISODE')),
  series_id TEXT, season_id TEXT, movie_id TEXT, episode_id TEXT,
  value INTEGER NOT NULL CHECK (value BETWEEN 1 AND 10), comment TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_user_series  ON ratings(user_id, target_type, series_id)  WHERE series_id  IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_user_season  ON ratings(user_id, target_type, season_id)  WHERE season_id  IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ratings_season_created ON ratings(season_id, updated);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_user_movie   ON ratings(user_id, target_type, movie_id)   WHERE movie_id   IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_user_episode ON ratings(user_id, target_type, episode_id) WHERE episode_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS watch_history (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN ('EPISODE','MOVIE')), episode_id TEXT, movie_id TEXT,
  progress_sec REAL NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_history_user_episode ON watch_history(user_id, target_type, episode_id) WHERE episode_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_history_user_movie   ON watch_history(user_id, target_type, movie_id)   WHERE movie_id   IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_history_user_updated ON watch_history(user_id, updated DESC);

CREATE TABLE IF NOT EXISTS watchlist_items (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  series_id TEXT REFERENCES series(id) ON DELETE CASCADE, movie_id TEXT REFERENCES movies(id) ON DELETE CASCADE,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_series ON watchlist_items(user_id, series_id) WHERE series_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_movie  ON watchlist_items(user_id, movie_id)  WHERE movie_id  IS NOT NULL;

CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  notify_on_new_episode INTEGER NOT NULL DEFAULT 1, notify_langs TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
  UNIQUE(user_id, series_id)
);

CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '',
  is_read INTEGER NOT NULL DEFAULT 0, dedupe_key TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created DESC);

CREATE TABLE IF NOT EXISTS user_collections (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS collection_items (
  id TEXT PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
  series_id TEXT REFERENCES series(id) ON DELETE CASCADE, movie_id TEXT REFERENCES movies(id) ON DELETE CASCADE,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_items_series ON collection_items(collection_id, series_id) WHERE series_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_items_movie  ON collection_items(collection_id, movie_id)  WHERE movie_id  IS NOT NULL;

CREATE TABLE IF NOT EXISTS forum_categories (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '',
  "order" INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS forum_threads (
  id TEXT PRIMARY KEY, category_id TEXT NOT NULL REFERENCES forum_categories(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL,
  is_pinned INTEGER NOT NULL DEFAULT 0, is_locked INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_threads_category_created ON forum_threads(category_id, created DESC);
CREATE TABLE IF NOT EXISTS forum_posts (
  id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES forum_threads(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, content TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_thread_created ON forum_posts(thread_id, created ASC);

CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, subject TEXT NOT NULL,
  priority TEXT NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH','URGENT')),
  status TEXT NOT NULL CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')),
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tickets_user_updated ON tickets(user_id, updated DESC);
CREATE TABLE IF NOT EXISTS ticket_messages (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, content TEXT NOT NULL,
  is_staff INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_created ON ticket_messages(ticket_id, created ASC);

CREATE TABLE IF NOT EXISTS profile_favorites (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 3),
  series_id TEXT REFERENCES series(id) ON DELETE CASCADE, movie_id TEXT REFERENCES movies(id) ON DELETE CASCADE,
  created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(user_id, rank)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY, actor_id TEXT REFERENCES users(id) ON DELETE SET NULL, action TEXT NOT NULL,
  target_type TEXT, target_id TEXT, metadata TEXT NOT NULL DEFAULT '{}', ip TEXT, user_agent TEXT, created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created DESC);

CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT 'null', updated TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS rate_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0, reset_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rate_limits_reset ON rate_limits(reset_at);

-- Gemeldete defekte Streams (ein offener Eintrag je Ziel+URL, Zähler steigt mit jeder Meldung)
CREATE TABLE IF NOT EXISTS stream_reports (
  id TEXT PRIMARY KEY, target_type TEXT NOT NULL CHECK (target_type IN ('EPISODE','MOVIE')), target_id TEXT NOT NULL,
  url TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', lang TEXT NOT NULL DEFAULT '',
  count INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','FIXED','IGNORED')),
  first_user_id TEXT, note TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stream_reports_status ON stream_reports(status, count DESC);
CREATE INDEX IF NOT EXISTS idx_stream_reports_target ON stream_reports(target_type, target_id);

-- Ergebnis des automatischen Link-Checks je URL
CREATE TABLE IF NOT EXISTS stream_checks (
  url TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'UNKNOWN', http_code INTEGER, note TEXT NOT NULL DEFAULT '',
  fail_count INTEGER NOT NULL DEFAULT 0, checked_at TEXT NOT NULL, last_ok_at TEXT NOT NULL DEFAULT ''
);
