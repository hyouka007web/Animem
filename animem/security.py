"""Passwörter, Token, TOTP (RFC 6238), Rate-Limits, Hilfen für JSON-Antworten."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

# ---- Passwörter & Token --------------------------------------------------------------

_DUMMY_HASH = generate_password_hash("animem-dummy-password")


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Prüft ein Passwort. Ohne Treffer wird trotzdem gehasht (gleichmäßige Antwortzeit)."""
    if not password_hash:
        check_password_hash(_DUMMY_HASH, password)
        return False
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---- TOTP ----------------------------------------------------------------------------

STEP = 30
DIGITS = 6


def totp_secret(n_bytes: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(n_bytes)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = DIGITS) -> str:
    padded = secret_b32.upper().replace(" ", "") + "=" * (-len(secret_b32.replace(" ", "")) % 8)
    key = base64.b32decode(padded)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_now(secret_b32: str, at: float | None = None) -> str:
    return _hotp(secret_b32, int((at if at is not None else time.time()) // STEP))


def verify_totp(secret_b32: str, token: str, at: float | None = None) -> bool:
    token = "".join(str(token).split())
    if len(token) != DIGITS or not token.isdigit():
        return False
    counter = int((at if at is not None else time.time()) // STEP)
    ok = False
    for delta in (0, -1, 1):  # eine Stufe Toleranz für Uhrabweichung
        if hmac.compare_digest(_hotp(secret_b32, counter + delta), token):
            ok = True
    return ok


def otpauth_uri(secret: str, account: str, issuer: str = "Animem") -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}&algorithm=SHA1"


def recovery_codes(count: int = 8) -> list[str]:
    return [secrets.token_hex(5) for _ in range(count)]


# ---- Client-IP & Rate-Limit ----------------------------------------------------------

def client_ip() -> str:
    # Mit TRUST_PROXY=1 setzt ProxyFix remote_addr korrekt aus X-Forwarded-For.
    return (request.remote_addr or "unknown")[:100]


def rate_limit(scope: str, limit: int, window_seconds: int, key: str | None = None):
    """Gibt (erlaubt, retry_after_sekunden) zurück. Zähler liegen in der Datenbank."""
    k = f"{scope}:{key or client_ip()}"
    now = time.time()
    with db.transaction() as conn:
        r = conn.execute("SELECT count, reset_at FROM rate_limits WHERE key=?", (k,)).fetchone()
        if r is None or r["reset_at"] <= now:
            count, reset_at = 1, now + window_seconds
            conn.execute(
                "INSERT INTO rate_limits (key, count, reset_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET count=excluded.count, reset_at=excluded.reset_at",
                (k, count, reset_at),
            )
        else:
            count, reset_at = r["count"] + 1, r["reset_at"]
            conn.execute("UPDATE rate_limits SET count=? WHERE key=?", (count, k))
        if secrets.randbelow(100) == 0:
            conn.execute("DELETE FROM rate_limits WHERE reset_at < ?", (now - 3600,))
    if count <= limit:
        return True, 0
    return False, max(1, int(reset_at - now))


def limited_response(retry_after: int):
    resp = jsonify(error="Zu viele Anfragen. Bitte kurz warten und erneut versuchen.")
    resp.status_code = 429
    resp.headers["Retry-After"] = str(retry_after)
    return resp


# ---- JSON-Helfer ---------------------------------------------------------------------

def ok(data=None, status=200):
    resp = jsonify(data if data is not None else {"success": True})
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    return resp


def fail(message, status=400):
    resp = jsonify(error=message)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    return resp
