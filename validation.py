"""Eingabe-Validierung (Ersatz für zod). Fehler werden als ValidationError mit deutscher Meldung geworfen."""
import re
from urllib.parse import urlparse

_max = max  # text()/integer() haben Parameter namens min/max

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
MEDIA_RE = re.compile(r"^/api/media/[A-Za-z0-9_-]+$")


class ValidationError(Exception):
    pass


def as_dict(data):
    if not isinstance(data, dict):
        raise ValidationError("Ungültige Anfrage.")
    return data


def text(data, key, *, min=0, max=500, default="", label=None, required=False):
    value = data.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValidationError(f"{label or key}: ungültiger Wert.")
    value = value.strip()
    if (required or min) and len(value) < _max(min, 1):
        raise ValidationError(f"{label or key}: mindestens {_max(min, 1)} Zeichen erforderlich.")
    if len(value) > max:
        raise ValidationError(f"{label or key}: höchstens {max} Zeichen erlaubt.")
    return value


def integer(data, key, *, min=None, max=None, label=None):
    value = data.get(key)
    try:
        if isinstance(value, bool):
            raise ValueError
        value = int(str(value).strip()) if not isinstance(value, int) else value
    except (TypeError, ValueError):
        raise ValidationError(f"{label or key}: ganze Zahl erforderlich.")
    if min is not None and value < min or max is not None and value > max:
        raise ValidationError(f"{label or key}: Wert außerhalb des erlaubten Bereichs.")
    return value


def choice(data, key, options, default=None, label=None):
    value = data.get(key, default)
    if value not in options:
        raise ValidationError(f"{label or key}: ungültige Auswahl.")
    return value


def https_url(value, label="URL"):
    if not isinstance(value, str):
        raise ValidationError(f"{label}: ungültig.")
    value = value.strip()
    if len(value) > 2000:
        raise ValidationError(f"{label}: zu lang.")
    try:
        p = urlparse(value)
    except ValueError:
        raise ValidationError(f"{label}: ungültig.")
    if p.scheme != "https" or not p.netloc or p.username or p.password:
        raise ValidationError("Nur HTTPS-URLs sind erlaubt.")
    return value


def media_url(value, optional=False, label="Bild-URL"):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{label}: ungültig.")
    value = value.strip()
    if not value:
        if optional:
            return ""
        raise ValidationError(f"{label}: erforderlich.")
    if MEDIA_RE.match(value):
        return value
    try:
        return https_url(value, label)
    except ValidationError:
        raise ValidationError("Es muss eine HTTPS-URL oder eine interne Medien-URL sein.")


def streams(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("Mindestens ein Stream ist erforderlich.")
    if len(value) > 10:
        raise ValidationError("Höchstens 10 Streams erlaubt.")
    out = []
    for s in value:
        if not isinstance(s, dict):
            raise ValidationError("Ungültiger Stream.")
        out.append({"label": text(s, "label", max=60, label="Stream-Name"), "url": https_url(s.get("url", ""), "Stream-URL")})
    return out


def name_list(value, max_items, label):
    if value is None:
        return []
    if isinstance(value, str):
        value = [v for v in re.split(r"[,\n]", value)]
    if not isinstance(value, list) or len(value) > max_items:
        raise ValidationError(f"{label}: ungültige Liste.")
    out, seen = [], set()
    for v in value:
        if not isinstance(v, str):
            raise ValidationError(f"{label}: ungültiger Eintrag.")
        v = v.strip()
        if not v:
            continue
        if len(v) > 80:
            raise ValidationError(f"{label}: Eintrag zu lang.")
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


# ---- Zusammengesetzte Schemata -----------------------------------------------------------

def registration(data):
    data = as_dict(data)
    username = text(data, "username", min=3, max=32, label="Benutzername")
    if not USERNAME_RE.match(username):
        raise ValidationError("Benutzername: nur Buchstaben, Zahlen und Unterstriche.")
    email = text(data, "email", min=3, max=254, label="E-Mail")
    if not EMAIL_RE.match(email):
        raise ValidationError("Bitte eine gültige E-Mail-Adresse eingeben.")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValidationError("Das Passwort muss 8 bis 128 Zeichen lang sein.")
    return {"username": username, "email": email, "password": password}


def episode(data):
    data = as_dict(data)
    ep_id = data.get("id")
    return {
        "id": ep_id if isinstance(ep_id, str) and ep_id else None,
        "number": integer(data, "number", min=1, max=10000, label="Folgennummer"),
        "title": text(data, "title", min=1, max=200, label="Folgentitel"),
        "streams": streams(data.get("streams")),
    }


def season(data):
    data = as_dict(data)
    season_id = data.get("id")
    eps = data.get("episodes") or []
    if not isinstance(eps, list) or len(eps) > 500:
        raise ValidationError("Ungültige Folgenliste.")
    parsed = [episode(e) for e in eps]
    numbers = [e["number"] for e in parsed]
    if len(numbers) != len(set(numbers)):
        raise ValidationError("Folgennummern müssen innerhalb einer Staffel eindeutig sein.")
    return {
        "id": season_id if isinstance(season_id, str) and season_id else None,
        "number": integer(data, "number", min=1, max=1000, label="Staffelnummer"),
        "title": text(data, "title", max=200, label="Staffeltitel"),
        "episodes": parsed,
    }


def series(data):
    data = as_dict(data)
    seasons_raw = data.get("seasons") or []
    if not isinstance(seasons_raw, list) or len(seasons_raw) > 50:
        raise ValidationError("Ungültige Staffelliste.")
    seasons = [season(s) for s in seasons_raw]
    numbers = [s["number"] for s in seasons]
    if len(numbers) != len(set(numbers)):
        raise ValidationError("Staffelnummern müssen eindeutig sein.")
    return {
        "title": text(data, "title", min=1, max=200, label="Titel"),
        "description": text(data, "description", max=5000, label="Beschreibung"),
        "thumbnail_url": media_url(data.get("thumbnailUrl"), label="Poster"),
        "banner_url": media_url(data.get("bannerUrl"), optional=True, label="Banner"),
        "status": choice(data, "status", ("DRAFT", "PUBLISHED", "ARCHIVED"), "DRAFT", "Status"),
        "genres": name_list(data.get("genres"), 50, "Genres"),
        "tags": name_list(data.get("tags"), 100, "Tags"),
        "seasons": seasons,
    }


def movie(data, partial=False):
    data = as_dict(data)
    out = {}

    def has(k):
        return (k in data) if partial else True

    if has("title"):
        out["title"] = text(data, "title", min=1, max=200, label="Titel")
    if has("description"):
        out["description"] = text(data, "description", max=5000, label="Beschreibung")
    if has("thumbnailUrl"):
        out["thumbnail_url"] = media_url(data.get("thumbnailUrl"), label="Poster")
    if has("bannerUrl"):
        out["banner_url"] = media_url(data.get("bannerUrl"), optional=True, label="Banner")
    if has("streams"):
        out["streams"] = streams(data.get("streams"))
    if has("status"):
        out["status"] = choice(data, "status", ("DRAFT", "PUBLISHED"), "DRAFT", "Status")
    if has("genres"):
        out["genres"] = name_list(data.get("genres"), 50, "Genres")
    if has("tags"):
        out["tags"] = name_list(data.get("tags"), 100, "Tags")
    return out


def rating(data):
    data = as_dict(data)
    target = choice(data, "targetType", ("SERIES", "MOVIE", "EPISODE"), label="Zieltyp")
    ids = {"SERIES": data.get("seriesId"), "MOVIE": data.get("movieId"), "EPISODE": data.get("episodeId")}
    present = [k for k, v in ids.items() if v]
    if present != [target] or not isinstance(ids[target], str) or len(ids[target]) > 64:
        raise ValidationError("Genau eine passende Ziel-ID ist erforderlich.")
    return {
        "target_type": target,
        "target_id": ids[target],
        "value": integer(data, "value", min=1, max=10, label="Bewertung"),
        "comment": text(data, "comment", max=2000, label="Kommentar"),
    }


def one_target(data, series_key="seriesId", movie_key="movieId"):
    data = as_dict(data)
    sid, mid = data.get(series_key), data.get(movie_key)
    if bool(sid) == bool(mid) or not isinstance(sid or mid, str) or len(sid or mid) > 64:
        raise ValidationError("Genau eine Serie oder ein Film muss angegeben werden.")
    return ("series_id", sid) if sid else ("movie_id", mid)
