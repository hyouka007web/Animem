"""Benachrichtigungen für abonnierte Serien – mit Sprachfilter pro Nutzer (und pro Abo).

Idee: Vor und nach jeder Änderung an einer Serie wird festgehalten, welche (Folge, Sprache)-Kombinationen
abrufbar sind. Der Unterschied sind die "neuen Inhalte". Jeder Abonnent bekommt nur die Teile, die zu
seinen Sprachen passen, und wird dabei aus SEINER Sicht eingeordnet:

  * Staffel war in seinen Sprachen noch nicht verfügbar        -> "Neue Staffel"
  * Folge war in seinen Sprachen noch nicht verfügbar          -> "Neue Folge"
  * Folge war schon da, jetzt in einer weiteren seiner Sprachen -> "Neue Sprache" (abschaltbar)

Beispiel: Wer nur GerDub wählt, bekommt nichts, wenn Staffel 2 zuerst nur mit Untertiteln erscheint –
aber eine Meldung "Staffel 2 jetzt auf Deutsch synchronisiert", sobald die Synchro dazukommt.
"""
import hashlib
import json

from . import db
from .langs import ALL, join_short, ordered

MAX_PER_SAVE = 4  # höchstens so viele Meldungen pro Nutzer und Speichervorgang


def snapshot(series_id):
    """{(episode_id, lang): (season_no, episode_no)} aller abrufbaren Streams einer veröffentlichten Serie."""
    series = db.get("series", series_id)
    if not series or series["status"] != "PUBLISHED":
        return {}
    out = {}
    for r in db.rows(
        "SELECT se.number AS sn, e.number AS en, e.id AS eid, e.streams FROM episodes e "
        "JOIN seasons se ON se.id = e.season_id WHERE se.series_id = ? AND e.status = 'PUBLISHED'", (series_id,)
    ):
        for s in r["streams"] or []:
            if s.get("lang"):
                out[(r["eid"], s["lang"])] = (r["sn"], r["en"])
    return out


def _ranges(numbers):
    nums = sorted(set(numbers))
    parts, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            parts.append((start, prev)); start = prev = n
    if start is not None:
        parts.append((start, prev))
    return ", ".join(f"E{a}" if a == b else f"E{a}–E{b}" for a, b in parts)


def _as_list(value):
    """Sprachlisten stammen aus JOINs mit Alias-Spalten und kommen dort als JSON-Text an."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return value if isinstance(value, list) else []


def effective_langs(user_langs, sub_langs):
    """Eigene Auswahl für die Serie, sonst die Profil-Einstellung."""
    langs = _as_list(sub_langs) if sub_langs is not None else _as_list(user_langs)
    return {l for l in langs if l in ALL}


def _messages_for(title, base_url, fb, fa, want_new_langs):
    """Meldungen (kind, text, link, key_parts) für EINEN Nutzer aus gefilterten Vorher/Nachher-Zuständen."""
    new = {k: v for k, v in fa.items() if k not in fb}
    if not new:
        return []
    known_seasons = {v[0] for v in fb.values()}
    known_eps = {k[0] for k in fb}
    by_season = {}
    for (eid, lang), (sn, en) in new.items():
        by_season.setdefault(sn, {}).setdefault((eid, en), set()).add(lang)
    out = []
    for sn in sorted(by_season):
        eps = by_season[sn]
        langs = set().union(*eps.values())
        link = f"{base_url}?season={sn}"
        if sn not in known_seasons:
            nums = _ranges([en for (_e, en) in eps])
            out.append(("NEW_SEASON", f"{title}: Staffel {sn} ist jetzt verfügbar ({join_short(langs)}, {nums}).", link,
                        [(eid, l) for (eid, _en), ls in eps.items() for l in ls]))
            continue
        fresh = {(eid, en): ls for (eid, en), ls in eps.items() if eid not in known_eps}
        if fresh:
            fl = set().union(*fresh.values())
            nums = _ranges([en for (_e, en) in fresh])
            link_ep = link
            if len(fresh) == 1:
                (_eid, en0), = fresh.keys()
                link_ep = f"{base_url}/s/{sn}/e/{en0}"
            noun = "Neue Folge" if len(fresh) == 1 else "Neue Folgen"
            out.append(("NEW_EPISODE", f"{title}: {noun} in Staffel {sn} – {nums} ({join_short(fl)}).", link_ep,
                        [(eid, l) for (eid, _en), ls in fresh.items() for l in ls]))
        extra = {(eid, en): ls for (eid, en), ls in eps.items() if eid in known_eps}
        if extra and want_new_langs:
            el = set().union(*extra.values())
            nums = _ranges([en for (_e, en) in extra])
            out.append(("NEW_LANGUAGE", f"{title}: Staffel {sn} jetzt auch {join_short(el)} – {nums}.", link,
                        [(eid, l) for (eid, _en), ls in extra.items() for l in ls]))
    return out


def notify_changes(series_id, before, after):
    """Vergleicht Zustände, aktualisiert 'zuletzt aktualisiert' und verschickt Meldungen. Gibt die Zahl der Meldungen zurück."""
    new = {k: v for k, v in after.items() if k not in before}
    if not new:
        return 0
    series = db.get("series", series_id)
    if not series:
        return 0

    # "Zuletzt aktualisiert": neueste neue Folge als Notiz merken
    sn, en = max(new.values())
    langs = {k[1] for k in new}
    db.update("series", series_id, {"content_updated": db.utcnow(), "last_update_note": f"Staffel {sn} · Folge {en} ({join_short(langs)})"})

    count = 0
    subs = db.rows(
        "SELECT s.id, s.user_id, s.notify_langs AS sub_langs, u.notify_langs AS user_langs, u.notify_new_langs AS new_langs "
        "FROM subscriptions s JOIN users u ON u.id = s.user_id "
        "WHERE s.series_id = ? AND s.notify_on_new_episode = 1 AND u.is_banned = 0", (series_id,))
    base_url = f"/series/{series['slug']}"
    for sub in subs:
        langs = effective_langs(sub["user_langs"], sub["sub_langs"])
        if not langs:
            continue
        fb = {k: v for k, v in before.items() if k[1] in langs}
        fa = {k: v for k, v in after.items() if k[1] in langs}
        msgs = _messages_for(series["title"], base_url, fb, fa, bool(sub["new_langs"]))
        for kind, message, link, parts in msgs[:MAX_PER_SAVE]:
            key = hashlib.sha1((kind + series_id + "|".join(sorted(f"{e}:{l}" for e, l in parts))).encode()).hexdigest()
            if db.row("SELECT 1 AS x FROM notifications WHERE user_id=? AND dedupe_key=?", (sub["user_id"], key)):
                continue
            db.insert("notifications", {"user_id": sub["user_id"], "type": kind, "message": message, "link": link,
                                        "is_read": False, "dedupe_key": key})
            count += 1
    return count


# ---- Verwaltung der Meldungen eines Nutzers -------------------------------------------------

def unread_count(user_id):
    return db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)) or 0


def mark_read(user_id, ids=None):
    if ids:
        marks = ",".join("?" for _ in ids)
        db.run(f"UPDATE notifications SET is_read=1 WHERE user_id=? AND id IN ({marks})", [user_id, *ids])
    else:
        db.run("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))
