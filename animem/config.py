"""Konfiguration aus Umgebungsvariablen / .env (ohne Zusatzpakete)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv():
    for name in (".env", ".env.local"):
        path = BASE_DIR / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _split(*names):
    out = []
    for name in names:
        out += [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]
    return out


def build_config():
    load_dotenv()
    data_dir = BASE_DIR / "data"
    return {
        "DB_PATH": os.environ.get("ANIMEM_DB_PATH") or str(data_dir / "animem.db"),
        "STORAGE_DIR": os.environ.get("ANIMEM_STORAGE_DIR") or str(data_dir / "uploads"),
        "OWNER_EMAILS": [v.lower() for v in _split("OWNER_EMAIL", "OWNER_EMAILS")],
        "OWNER_USERNAMES": _split("OWNER_USERNAME", "OWNER_USERNAMES"),
        "TRUST_PROXY": os.environ.get("TRUST_PROXY", "0") == "1",
        "MAX_CONTENT_LENGTH": 11 * 1024 * 1024,
        "JSON_AS_ASCII": False,
        "DEBUG_ERRORS": os.environ.get("FLASK_DEBUG", "0") == "1",
        # Automatischer Link-Check: alle N Stunden (0 = aus). Läuft als Hintergrund-Thread, nur ein Worker gleichzeitig.
        "LINKCHECK_INTERVAL_HOURS": float(os.environ.get("LINKCHECK_INTERVAL_HOURS", "24") or 0),
    }
