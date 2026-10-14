"""Metadaten-Import aus AniList (GraphQL) und Jikan/MyAnimeList (REST). Nur Standardbibliothek.

Liefert ein Ergebnis im Format des Admin-Editors (camelCase). Es werden Titel, Beschreibung, Cover, Genres,
Tags, Jahr, Status und die Staffeln samt Folgenliste übernommen – Streams bleiben leer (Folgen sind dann
"angekündigt", bis Streams eingetragen werden).
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ANILIST_URL = "https://graphql.anilist.co"
JIKAN_URL = "https://api.jikan.moe/v4"
SERIES_FORMATS = ["TV", "TV_SHORT", "ONA"]
MAX_HOPS = 10
MAX_EPISODES = 500


class MetadataError(Exception):
    pass


def http_json(url, payload=None, timeout=20):
    headers = {"Accept": "application/json", "User-Agent": "Animem/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise MetadataError("Nicht gefunden.")
        if e.code == 429:
            raise MetadataError("Der Anbieter hat zu viele Anfragen erhalten – bitte in einer Minute erneut versuchen.")
        raise MetadataError(f"Der Anbieter antwortet mit Fehler {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise MetadataError("Anbieter nicht erreichbar (keine Internetverbindung oder Dienst down).")
    except ValueError:
        raise MetadataError("Ungültige Antwort des Anbieters.")


HTTP = http_json   # in Tests austauschbar
SLEEP = time.sleep


def clean_text(text, limit=5000):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</?(i|b|em|strong|p|span)[^>]*>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def _date(d):
    if not d or not d.get("year"):
        return ""
    return f"{d['year']:04d}-{(d.get('month') or 1):02d}-{(d.get('day') or 1):02d}"


def _iso_from_ts(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


# ======================================================================================
# AniList
# ======================================================================================

_SEARCH_Q = """query ($search: String, $formats: [MediaFormat]) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: ANIME, format_in: $formats, sort: SEARCH_MATCH) {
      id idMal title { romaji english native } synonyms format status seasonYear startDate { year } episodes
      coverImage { large extraLarge } description(asHtml: false)
    }
  }
}"""

_MEDIA_Q = """query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id idMal title { romaji english native } synonyms format status seasonYear startDate { year month day } episodes
    description(asHtml: false) genres tags { name rank isMediaSpoiler }
    coverImage { large extraLarge } bannerImage
    nextAiringEpisode { airingAt episode }
    airingSchedule(notYetAired: true, perPage: 60) { nodes { episode airingAt } }
    relations { edges { relationType node { id type format title { romaji english } } } }
  }
}"""

_STATUS = {"FINISHED": "FINISHED", "RELEASING": "AIRING", "NOT_YET_RELEASED": "UPCOMING", "CANCELLED": "CANCELLED", "HIATUS": "HIATUS"}


def _anilist(query, variables):
    data = HTTP(ANILIST_URL, {"query": query, "variables": variables})
    if data.get("errors") and not data.get("data"):
        raise MetadataError("AniList: " + str(data["errors"][0].get("message", "Fehler")))
    return data.get("data") or {}


def _display_title(t):
    return (t or {}).get("english") or (t or {}).get("romaji") or (t or {}).get("native") or "Unbekannt"


def _all_titles(m):
    t = m.get("title") or {}
    return [x for x in [t.get("english"), t.get("romaji"), t.get("native"), *(m.get("synonyms") or [])] if x]


def anilist_search(q, kind="series"):
    formats = ["MOVIE"] if kind == "movie" else SERIES_FORMATS
    media = _anilist(_SEARCH_Q, {"search": q, "formats": formats}).get("Page", {}).get("media") or []
    return [{
        "provider": "anilist", "id": m["id"], "title": _display_title(m.get("title")), "titles": _all_titles(m),
        "year": m.get("seasonYear") or (m.get("startDate") or {}).get("year"), "episodes": m.get("episodes"),
        "cover": (m.get("coverImage") or {}).get("large") or "", "format": m.get("format"),
        "status": _STATUS.get(m.get("status"), ""), "description": clean_text(m.get("description"), 220),
    } for m in media]


def _anilist_media(mid):
    media = _anilist(_MEDIA_Q, {"id": int(mid)}).get("Media")
    if not media:
        raise MetadataError("Eintrag nicht gefunden.")
    return media


def _season_from_anilist(m):
    sched = {}
    for n in (m.get("airingSchedule") or {}).get("nodes") or []:
        if n.get("episode") and n.get("airingAt"):
            sched[n["episode"]] = _iso_from_ts(n["airingAt"])
    nxt = m.get("nextAiringEpisode") or {}
    if nxt.get("episode") and nxt.get("airingAt"):
        sched.setdefault(nxt["episode"], _iso_from_ts(nxt["airingAt"]))
    total = m.get("episodes") or (max(sched) if sched else 0) or ((nxt.get("episode") or 1) - 1 if nxt else 0)
    total = min(int(total or 0), MAX_EPISODES)
    start = _date(m.get("startDate"))
    eps = []
    for n in range(1, total + 1):
        eps.append({"number": n, "title": f"Folge {n}", "airedAt": sched.get(n) or (start if n == 1 else ""), "streams": []})
    return {"sourceId": m["id"], "malId": m.get("idMal"), "sourceTitle": _display_title(m.get("title")),
            "cover": (m.get("coverImage") or {}).get("extraLarge") or (m.get("coverImage") or {}).get("large") or "",
            "banner": m.get("bannerImage") or "", "year": m.get("seasonYear") or (m.get("startDate") or {}).get("year"),
            "status": _STATUS.get(m.get("status"), ""), "episodes": eps}


def _relation(m, kind):
    for e in (m.get("relations") or {}).get("edges") or []:
        n = e.get("node") or {}
        if e.get("relationType") == kind and n.get("type") == "ANIME" and n.get("format") in SERIES_FORMATS:
            return n["id"]
    return None


def anilist_fetch(mid, follow=True):
    root = _anilist_media(mid)
    chain = [root]
    seen = {root["id"]}
    if follow:
        cur = root
        for _ in range(MAX_HOPS):                       # zurück zu Staffel 1
            pid = _relation(cur, "PREQUEL")
            if not pid or pid in seen:
                break
            cur = _anilist_media(pid); seen.add(cur["id"]); chain.insert(0, cur)
        cur = root
        for _ in range(MAX_HOPS):                       # vorwärts zu späteren Staffeln
            sid = _relation(cur, "SEQUEL")
            if not sid or sid in seen:
                break
            cur = _anilist_media(sid); seen.add(cur["id"]); chain.append(cur)
    first = chain[0]
    seasons = [_season_from_anilist(m) for m in chain]
    tags = [t["name"] for t in (first.get("tags") or []) if not t.get("isMediaSpoiler") and (t.get("rank") or 0) >= 60][:12]
    main = _display_title(first.get("title"))
    alts = []
    for m in chain:
        for t in _all_titles(m):
            if t != main and t not in alts:
                alts.append(t)
    res = _result("anilist", main, alts[:30], clean_text(first.get("description")), first.get("genres") or [], tags, seasons, first.get("format"))
    res["malIds"] = [m.get("idMal") for m in chain]
    return res


# ======================================================================================
# Jikan (MyAnimeList)
# ======================================================================================

_JIKAN_STATUS = {"Finished Airing": "FINISHED", "Currently Airing": "AIRING", "Not yet aired": "UPCOMING"}


def _jikan(path):
    SLEEP(0.4)  # Jikan erlaubt etwa 3 Anfragen pro Sekunde
    return HTTP(JIKAN_URL + path)


def _jikan_titles(a):
    seen = []
    for t in (a.get("titles") or []):
        if t.get("title") and t["title"] not in seen:
            seen.append(t["title"])
    for k in ("title_english", "title", "title_japanese"):
        if a.get(k) and a[k] not in seen:
            seen.append(a[k])
    return seen


def _jikan_main(a):
    return a.get("title_english") or a.get("title") or a.get("title_japanese") or "Unbekannt"


def jikan_search(q, kind="series"):
    kinds = "movie" if kind == "movie" else "tv"
    data = _jikan(f"/anime?q={urllib.parse.quote(q)}&limit=10&type={kinds}&sfw=true").get("data") or []
    return [{
        "provider": "jikan", "id": a["mal_id"], "title": _jikan_main(a), "titles": _jikan_titles(a),
        "year": a.get("year") or ((a.get("aired") or {}).get("prop") or {}).get("from", {}).get("year"), "episodes": a.get("episodes"),
        "cover": ((a.get("images") or {}).get("jpg") or {}).get("large_image_url") or ((a.get("images") or {}).get("jpg") or {}).get("image_url") or "",
        "format": a.get("type"), "status": _JIKAN_STATUS.get(a.get("status"), ""), "description": clean_text(a.get("synopsis"), 220),
    } for a in data]


def _jikan_full(mid):
    a = _jikan(f"/anime/{int(mid)}/full").get("data")
    if not a:
        raise MetadataError("Eintrag nicht gefunden.")
    return a


def jikan_episodes(mid):
    """Folgentitel/-daten (Nummer -> (Titel, Datum)). Mehrere Seiten, höchstens MAX_EPISODES."""
    out, page = {}, 1
    while len(out) < MAX_EPISODES:
        res = _jikan(f"/anime/{int(mid)}/episodes?page={page}")
        for e in res.get("data") or []:
            n = e.get("mal_id")
            if n:
                out[n] = (e.get("title") or "", (e.get("aired") or "")[:10])
        if not (res.get("pagination") or {}).get("has_next_page"):
            break
        page += 1
    return out


def _season_from_jikan(a, with_titles):
    total = min(int(a.get("episodes") or 0), MAX_EPISODES)
    titles = {}
    if with_titles and a.get("mal_id"):
        try:
            titles = jikan_episodes(a["mal_id"])
        except MetadataError:
            titles = {}
    total = total or (max(titles) if titles else 0)
    start = ((a.get("aired") or {}).get("from") or "")[:10]
    eps = []
    for n in range(1, total + 1):
        t, d = titles.get(n, ("", ""))
        eps.append({"number": n, "title": t or f"Folge {n}", "airedAt": d or (start if n == 1 else ""), "streams": []})
    img = (a.get("images") or {}).get("jpg") or {}
    return {"sourceId": a["mal_id"], "malId": a["mal_id"], "sourceTitle": _jikan_main(a),
            "cover": img.get("large_image_url") or img.get("image_url") or "", "banner": "",
            "year": a.get("year") or (int(start[:4]) if start else None), "status": _JIKAN_STATUS.get(a.get("status"), ""), "episodes": eps}


def _jikan_related(a, relation):
    for r in a.get("relations") or []:
        if r.get("relation") == relation:
            for e in r.get("entry") or []:
                if e.get("type") == "anime":
                    return e["mal_id"]
    return None


def jikan_fetch(mid, follow=True, with_titles=True):
    root = _jikan_full(mid)
    chain, seen = [root], {root["mal_id"]}
    if follow:
        cur = root
        for _ in range(MAX_HOPS):
            pid = _jikan_related(cur, "Prequel")
            if not pid or pid in seen:
                break
            cur = _jikan_full(pid)
            if cur.get("type") not in ("TV", "ONA"):
                break
            seen.add(cur["mal_id"]); chain.insert(0, cur)
        cur = root
        for _ in range(MAX_HOPS):
            sid = _jikan_related(cur, "Sequel")
            if not sid or sid in seen:
                break
            cur = _jikan_full(sid)
            if cur.get("type") not in ("TV", "ONA"):
                break
            seen.add(cur["mal_id"]); chain.append(cur)
    first = chain[0]
    names = lambda key: [g["name"] for g in (first.get(key) or []) if g.get("name")]
    main = _jikan_main(first)
    alts = []
    for a in chain:
        for t in _jikan_titles(a):
            if t != main and t not in alts:
                alts.append(t)
    seasons = [_season_from_jikan(a, with_titles) for a in chain]
    return _result("jikan", main, alts[:30], clean_text(first.get("synopsis")), names("genres"), names("themes")[:12], seasons, first.get("type"))


# ======================================================================================
# Gemeinsames Ergebnis + Einstiegspunkte
# ======================================================================================

def _result(provider, title, alts, description, genres, tags, seasons, fmt):
    last_status = next((s["status"] for s in reversed(seasons) if s["status"]), "")
    status = "AIRING" if any(s["status"] == "AIRING" for s in seasons) else last_status
    return {
        "provider": provider, "format": fmt, "title": title, "altTitles": alts, "description": description,
        "thumbnailUrl": seasons[0]["cover"], "bannerUrl": seasons[0].get("banner", ""), "genres": genres, "tags": tags,
        "year": seasons[0]["year"], "airStatus": status,
        "seasons": [{"number": i, "title": "", "thumbnailUrl": s["cover"], "sourceTitle": s["sourceTitle"], "episodes": s["episodes"]}
                    for i, s in enumerate(seasons, 1)],
    }


def search(provider, q, kind="series"):
    q = (q or "").strip()
    if len(q) < 2:
        raise MetadataError("Bitte mindestens 2 Zeichen eingeben.")
    if provider == "jikan":
        return jikan_search(q, kind)
    return anilist_search(q, kind)


def fetch(provider, item_id, with_titles=True, follow=True):
    if provider == "jikan":
        return jikan_fetch(item_id, follow, with_titles)
    result = anilist_fetch(item_id, follow)
    mal_ids = result.pop("malIds", [])
    if with_titles:
        # Folgentitel über Jikan nachladen, wenn eine MyAnimeList-ID bekannt ist (AniList liefert keine Folgentitel)
        for season, mal in zip(result["seasons"], mal_ids):
            if not mal:
                continue
            try:
                titles = jikan_episodes(mal)
            except MetadataError:
                break  # Folgentitel sind optional – bei Problemen mit Jikan einfach ohne weitermachen
            for ep in season["episodes"]:
                t = titles.get(ep["number"])
                if t and t[0]:
                    ep["title"] = t[0]
                if t and t[1] and not ep["airedAt"]:
                    ep["airedAt"] = t[1]
    return result
