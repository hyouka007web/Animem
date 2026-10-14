"""Tests: Sprach-Labels, defekte Links & Link-Check, Metadaten-Import, Benachrichtigungen, Entdecken."""
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from animem import catalog, create_app, db, linkcheck, metadata, notify, services, streamtools
from test_app import Base


def eps(season, numbers, langs=("GERSUB",), aired=None, host="x.example.com"):
    out = []
    for n in numbers:
        streams = [{"lang": l, "label": l, "url": f"https://{host}/{season}/{n}/{l}"} for l in langs]
        out.append({"number": n, "title": f"E{n}", "streams": streams, "airedAt": (aired or {}).get(n, "")})
    return out


def payload(title, seasons, **extra):
    base = {"title": title, "description": "", "thumbnailUrl": f"https://img.example.com/{title}.jpg", "bannerUrl": "",
            "status": "PUBLISHED", "genres": extra.pop("genres", []), "tags": extra.pop("tags", []),
            "seasons": [{"number": n, "title": "", "thumbnailUrl": "", "episodes": e} for n, e in seasons.items()]}
    base.update(extra)
    return base


class Features(Base):
    def setUp(self):
        self.n = getattr(Features, "_n", 0) + 1
        Features._n = self.n
        self.adm_name = f"fadm{self.n}"
        self.make_user(self.adm_name, "ADMIN")
        self.admin = self.client(); self.login(self.admin, self.adm_name)

    def series(self, title, seasons, **extra):
        r = self.admin.post("/api/series", json=payload(title, seasons, **extra))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def to_payload(self, full):
        return {"title": full["title"], "description": full["description"], "thumbnailUrl": full["thumbnail_url"], "bannerUrl": full["banner_url"],
                "status": full["status"], "genres": full["genres"], "tags": full["tags"], "altTitles": full["alt_titles"], "year": full["year"],
                "airStatus": full["air_status"],
                "seasons": [{"id": s["id"], "number": s["number"], "title": s["title"], "thumbnailUrl": s["thumbnail_url"],
                             "episodes": [{"id": e["id"], "number": e["number"], "title": e["title"], "airedAt": e["aired_at"], "streams": e["streams"]}
                                          for e in s["episodes"]]} for s in full["seasons"]]}

    def edit(self, series_id, fn):
        full = self.admin.get(f"/api/series/{series_id}").get_json()
        p = self.to_payload(full); fn(p)
        r = self.admin.patch(f"/api/series/{series_id}", json=p)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def user(self, name):
        name = f"{name}{self.n}"
        self.make_user(name); c = self.client(); self.login(c, name); c.name = name
        return c

    def notes(self, c):
        return c.get("/api/notifications").get_json()["items"]

    # ============================================================================ Sprachen
    def test_language_required_and_announced_episodes(self):
        bad = payload("Ohnelang", {1: [{"number": 1, "title": "E1", "streams": [{"label": "x", "url": "https://x.example.com/a"}]}]})
        self.assertEqual(self.admin.post("/api/series", json=bad).status_code, 400)
        bad["seasons"][0]["episodes"][0]["streams"][0]["lang"] = "KLINGON"
        self.assertEqual(self.admin.post("/api/series", json=bad).status_code, 400)
        dup = payload("Doppelt", {1: [{"number": 1, "title": "E1", "streams": [{"lang": "OMU", "label": "a", "url": "https://x.example.com/a"}] * 2}]})
        self.assertEqual(self.admin.post("/api/series", json=dup).status_code, 400)
        s = self.series("Angekuendigt", {1: eps(1, [1]) + [{"number": 2, "title": "E2", "streams": [], "airedAt": "2099-01-01"}]})
        e2 = s["seasons"][0]["episodes"][1]
        self.assertEqual((e2["status"], e2["aired_at"]), ("DRAFT", "2099-01-01"))   # ohne Stream = angekündigt
        page = self.client().get(f"/series/{s['slug']}").get_data(as_text=True)
        self.assertIn("Demnächst", page); self.assertIn("Folge 2", page)
        self.assertEqual(self.client().get(f"/series/{s['slug']}/s/1/e/2").status_code, 404)   # nicht abrufbar

    def test_player_languages_and_remembered_preference(self):
        s = self.series("Sprachen", {1: eps(1, [1], langs=("GERSUB", "GERDUB", "OMU"))})
        anon = self.client().get(f"/series/{s['slug']}/s/1/e/1").get_data(as_text=True)
        for l in ("GerDub", "GerSub", "OmU"):
            self.assertIn(f">{l}</button>", anon)                        # Sprach-Chips
        self.assertIn('data-lang=""', anon)                              # ohne gemerkte Sprache: alle
        u = self.user("lang")
        self.assertEqual(u.patch("/api/profile/preferences", json={"prefLang": "GERDUB"}).status_code, 200)
        page = u.get(f"/series/{s['slug']}/s/1/e/1").get_data(as_text=True)
        self.assertIn('data-lang="GERDUB"', page)                        # gemerkte Sprache kommt vom Server
        self.assertIn('<iframe src="https://x.example.com/1/1/GERDUB"', page)   # und der passende Stream startet
        self.assertEqual(u.patch("/api/profile/preferences", json={"prefLang": "KLINGON"}).status_code, 400)
        # Sprache gibt es nicht -> keine leere Seite
        s2 = self.series("NurSub", {1: eps(1, [1], langs=("GERSUB",))})
        self.assertIn('data-lang=""', u.get(f"/series/{s2['slug']}/s/1/e/1").get_data(as_text=True))

    def test_language_filter_and_badges_in_catalog(self):
        self.series("DubSerie", {1: eps(1, [1], langs=("GERDUB", "GERSUB"))})
        self.series("SubSerie", {1: eps(1, [1], langs=("GERSUB",))})
        dub = self.client().get("/series?lang=GERDUB").get_data(as_text=True)
        self.assertIn("DubSerie", dub); self.assertNotIn("SubSerie", dub)
        sub = self.client().get("/series?lang=GERSUB").get_data(as_text=True)
        self.assertIn("DubSerie", sub); self.assertIn("SubSerie", sub)
        self.assertIn('lang-badge l-gerdub">GerDub', dub)                # Badge auf der Karte

    # ============================================================================ Defekte Links
    def test_report_flow_and_admin_actions(self):
        s = self.series("Meldung", {1: eps(1, [1], langs=("GERSUB", "GERDUB"))})
        ep = s["seasons"][0]["episodes"][0]; bad = ep["streams"][0]["url"]
        url = f"/api/streams/report"
        body = {"targetType": "EPISODE", "targetId": ep["id"], "url": bad}
        c1 = self.client(ip="203.0.113.10")
        r = c1.post(url, json=body); self.assertEqual((r.status_code, r.get_json()["count"]), (200, 1))
        self.assertTrue(c1.post(url, json=body).get_json().get("already"))   # selbe Person, selber Stream: kein Doppelzähler
        self.assertEqual(self.client(ip="203.0.113.11").post(url, json=body).get_json()["count"], 2)
        self.assertEqual(self.client(ip="203.0.113.12").post(url, json=dict(body, url="https://fremd.example.com/x")).status_code, 404)
        self.assertEqual(self.client(ip="203.0.113.13").post(url, json=dict(body, targetType="SERIES")).status_code, 400)
        # Player markiert gemeldeten Stream (ab 2 Meldungen)
        page = self.client().get(f"/series/{s['slug']}/s/1/e/1").get_data(as_text=True)
        self.assertIn("gemeldet</small>", page)
        # Admin-Liste
        html = self.admin.get("/admin/reports").get_data(as_text=True)
        self.assertIn("2× gemeldet", html); self.assertIn("Meldung", html)
        self.assertEqual(self.client().get("/admin/reports").status_code, 302)
        with self.app.app_context():
            rep = db.row("SELECT * FROM stream_reports WHERE target_id=? AND url=?", (ep["id"], bad))
        # Ignorieren: weitere Meldungen zählen nicht mehr
        self.assertEqual(self.admin.patch(f"/api/admin/reports/{rep['id']}", json={"action": "ignore"}).status_code, 200)
        self.assertEqual(self.client(ip="203.0.113.14").post(url, json=body).get_json()["status"], "ignored")
        # Wieder öffnen und Stream entfernen
        self.admin.patch(f"/api/admin/reports/{rep['id']}", json={"action": "reopen"})
        self.assertEqual(self.admin.patch(f"/api/admin/reports/{rep['id']}", json={"action": "remove_stream"}).status_code, 200)
        full = self.admin.get(f"/api/series/{s['id']}").get_json()
        left = [x["lang"] for x in full["seasons"][0]["episodes"][0]["streams"]]
        self.assertEqual(left, ["GERDUB"])
        with self.app.app_context():
            self.assertEqual(db.row("SELECT status FROM stream_reports WHERE id=?", (rep["id"],))["status"], "FIXED")
        self.assertEqual(self.admin.patch(f"/api/admin/reports/{rep['id']}", json={"action": "boom"}).status_code, 400)

    def test_editing_link_closes_stale_report(self):
        s = self.series("Ersetzt", {1: eps(1, [1], langs=("GERSUB",))})
        ep = s["seasons"][0]["episodes"][0]
        self.client(ip="203.0.113.20").post("/api/streams/report", json={"targetType": "EPISODE", "targetId": ep["id"], "url": ep["streams"][0]["url"]})
        def swap(p): p["seasons"][0]["episodes"][0]["streams"][0]["url"] = "https://neu.example.com/ok"
        self.edit(s["id"], swap)
        with self.app.app_context():
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM stream_reports WHERE status='OPEN'"), db.scalar("SELECT COUNT(*) FROM stream_reports WHERE status='OPEN' AND target_id<>?", (ep["id"],)))
            self.assertEqual(db.row("SELECT status FROM stream_reports WHERE target_id=?", (ep["id"],))["status"], "FIXED")

    # ============================================================================ Link-Check
    def test_check_url_classification(self):
        ok = lambda u: (200, "<html>Video</html>")
        self.assertEqual(linkcheck.check_url("https://a", ok)["status"], "OK")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (404, ""))["status"], "FAIL")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (410, ""))["status"], "FAIL")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (500, ""))["status"], "FAIL")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (403, ""))["status"], "UNKNOWN")      # Anti-Bot ≠ tot
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (429, ""))["status"], "UNKNOWN")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (200, "<h1>File not found</h1>"))["status"], "FAIL")   # Soft-404
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (200, "Leider: Datei nicht gefunden"))["status"], "FAIL")
        self.assertEqual(linkcheck.check_url("https://a", lambda u: (200, "This video has been deleted"))["status"], "FAIL")
        def boom(u): raise TimeoutError()
        self.assertEqual(linkcheck.check_url("https://a", boom)["status"], "FAIL")
        def weird(u): raise ValueError("kaputt")
        self.assertEqual(linkcheck.check_url("https://a", weird)["status"], "UNKNOWN")

    def test_run_all_marks_dead_after_two_failures_and_flags_player(self):
        s = self.series("Check", {1: eps(1, [1], langs=("GERSUB", "GERDUB"), host="chk.example.com")})
        dead_url = "https://chk.example.com/1/1/GERSUB"; good_url = "https://chk.example.com/1/1/GERDUB"
        fake = lambda u: (404, "") if u == dead_url else (200, "ok")
        path = self.app.config["DB_PATH"]
        conn = db._connect(path); self.assertTrue(linkcheck.claim(conn)); conn.close()
        self.assertFalse(linkcheck.start_background(path, fake))                     # läuft schon -> kein Doppellauf
        linkcheck.run_all(path, fake, workers=2, pause=0)
        with self.app.app_context():
            self.assertEqual(db.row("SELECT status FROM stream_checks WHERE url=?", (dead_url,))["status"], "SUSPECT")   # 1. Fehlschlag
            self.assertEqual(db.row("SELECT status FROM stream_checks WHERE url=?", (good_url,))["status"], "OK")
        conn = db._connect(path); linkcheck.claim(conn); conn.close()
        res = linkcheck.run_all(path, fake, workers=2, pause=0)
        self.assertGreaterEqual(res["dead"], 1)
        with self.app.app_context():
            self.assertEqual(db.row("SELECT status FROM stream_checks WHERE url=?", (dead_url,))["status"], "DEAD")   # 2. Fehlschlag = tot
            st = linkcheck.get_state(db.get_db()); self.assertFalse(st["running"]); self.assertTrue(st["finished"])
        page = self.client().get(f"/series/{s['slug']}/s/1/e/1").get_data(as_text=True)
        self.assertIn("evtl. offline", page)                                           # im Player markiert
        self.assertLess(page.index(good_url), page.index(dead_url))                   # funktionierende zuerst
        self.assertIn(f'<iframe src="{good_url}"', page)                              # und als Standard geladen
        self.assertIn("Check", self.admin.get("/admin/reports").get_data(as_text=True))
        # Link repariert -> wieder OK, Zähler zurück
        fixed = lambda u: (200, "ok")
        conn = db._connect(path); linkcheck.claim(conn); conn.close(); linkcheck.run_all(path, fixed, workers=1, pause=0)
        with self.app.app_context():
            row = db.row("SELECT status, fail_count FROM stream_checks WHERE url=?", (dead_url,))
            self.assertEqual((row["status"], row["fail_count"]), ("OK", 0))

    def test_admin_check_endpoints(self):
        self.series("Endpunkt", {1: eps(1, [1], host="ep.example.com")})
        old = linkcheck.FETCH; linkcheck.FETCH = lambda u: (200, "ok")
        try:
            r = self.admin.post("/api/admin/streams/check", json={"url": "https://ep.example.com/1/1/GERSUB"})
            self.assertEqual(r.get_json()["status"], "OK")
            self.assertEqual(self.admin.post("/api/admin/streams/check", json={"url": "http://unsicher"}).status_code, 400)
            self.assertEqual(self.client().post("/api/admin/streams/check", json={"url": "https://x.example.com"}).status_code, 403)
            with self.app.app_context():
                db.run("DELETE FROM app_settings WHERE key='linkcheck_state'")
            self.assertTrue(self.admin.post("/api/admin/streams/check-all", json={}).get_json()["started"])
            for _ in range(60):
                st = self.admin.get("/api/admin/streams/check-status").get_json()
                if not st["running"]: break
                time.sleep(0.1)
            self.assertFalse(st["running"]); self.assertGreaterEqual(st["total"], 1)
        finally:
            linkcheck.FETCH = old

    # ============================================================================ Import
    def fake_anilist(self):
        def media(i, title, eps_n, seq=None, pre=None, mal=None, sched=None, year=2020):
            rel = [{"relationType": "SEQUEL", "node": {"id": seq, "type": "ANIME", "format": "TV", "title": {"romaji": "x"}}}] if seq else []
            rel += [{"relationType": "PREQUEL", "node": {"id": pre, "type": "ANIME", "format": "TV", "title": {"romaji": "x"}}}] if pre else []
            rel += [{"relationType": "SEQUEL", "node": {"id": 999, "type": "ANIME", "format": "MOVIE", "title": {"romaji": "Film"}}}]   # Filme zählen nicht als Staffel
            return {"id": i, "idMal": mal, "title": {"romaji": f"{title} romaji", "english": title, "native": f"{title}日本"}, "synonyms": ["AbkürzungX"],
                    "format": "TV", "status": "FINISHED" if i == 1 else "RELEASING", "seasonYear": year, "startDate": {"year": year, "month": 4, "day": 7},
                    "episodes": eps_n, "description": "Erste Zeile<br>Zweite &amp; Zeile", "genres": ["Action", "Drama"],
                    "tags": [{"name": "Magie", "rank": 80, "isMediaSpoiler": False}, {"name": "Spoiler", "rank": 90, "isMediaSpoiler": True}, {"name": "Selten", "rank": 10, "isMediaSpoiler": False}],
                    "coverImage": {"large": f"https://s4.anilist.co/{i}-l.jpg", "extraLarge": f"https://s4.anilist.co/{i}-xl.jpg"}, "bannerImage": f"https://s4.anilist.co/{i}-b.jpg",
                    "nextAiringEpisode": None, "airingSchedule": {"nodes": sched or []}, "relations": {"edges": rel}}
        db_ = {1: media(1, "Attack Test", 2, seq=2, mal=10), 2: media(2, "Attack Test 2", None, pre=1, mal=20, year=2021,
               sched=[{"episode": 1, "airingAt": 4102444800}, {"episode": 2, "airingAt": 4102531200}, {"episode": 3, "airingAt": 4102617600}])}
        def http(url, payload=None, **kw):
            if "anilist" in url:
                v = payload["variables"]
                if "search" in v:
                    return {"data": {"Page": {"media": [db_[1]]}}}
                return {"data": {"Media": db_[v["id"]]}}
            if url.endswith("/anime/10/episodes?page=1"):
                return {"data": [{"mal_id": 1, "title": "Der Anfang", "aired": "2013-04-07T00:00:00+00:00"}, {"mal_id": 2, "title": "Der Zweite", "aired": "2013-04-14T00:00:00+00:00"}], "pagination": {"has_next_page": False}}
            raise metadata.MetadataError("Nicht gefunden.")
        return http

    def test_metadata_import_anilist(self):
        old_http, old_sleep = metadata.HTTP, metadata.SLEEP
        metadata.HTTP, metadata.SLEEP = self.fake_anilist(), (lambda s: None)
        try:
            res = metadata.search("anilist", "attack")
            self.assertEqual(res[0]["title"], "Attack Test"); self.assertEqual(res[0]["year"], 2020); self.assertIn("Zeile", res[0]["description"])
            with self.assertRaises(metadata.MetadataError): metadata.search("anilist", "a")
            for start in (1, 2):                                   # egal ob man Staffel 1 oder 2 wählt: ganze Kette
                full = metadata.fetch("anilist", start, with_titles=True)
                self.assertEqual([s["number"] for s in full["seasons"]], [1, 2])      # Prequel/Sequel-Kette, Film ausgeschlossen
                self.assertEqual(full["title"], "Attack Test")
                self.assertEqual(full["thumbnailUrl"], "https://s4.anilist.co/1-xl.jpg")
                self.assertEqual(full["seasons"][1]["thumbnailUrl"], "https://s4.anilist.co/2-xl.jpg")   # eigenes Bild je Staffel
                self.assertIn("Magie", full["tags"]); self.assertNotIn("Spoiler", full["tags"]); self.assertNotIn("Selten", full["tags"])
                self.assertIn("Attack Test romaji", full["altTitles"]); self.assertIn("AbkürzungX", full["altTitles"]); self.assertNotIn("Attack Test", full["altTitles"])
                self.assertEqual(full["description"], "Erste Zeile\nZweite & Zeile")   # HTML bereinigt
                self.assertEqual(full["airStatus"], "AIRING"); self.assertEqual(full["year"], 2020)
                s1, s2 = full["seasons"]
                self.assertEqual([e["title"] for e in s1["episodes"]], ["Der Anfang", "Der Zweite"])   # Folgentitel via Jikan
                self.assertEqual(s1["episodes"][0]["airedAt"], "2020-04-07")          # Startdatum aus AniList
                self.assertEqual(s1["episodes"][1]["airedAt"], "2013-04-14")          # fehlende Daten ergänzt Jikan
                self.assertEqual(len(s2["episodes"]), 3)                                  # Anzahl aus Sendeplan, wenn unbekannt
                self.assertEqual(s2["episodes"][1]["airedAt"], "2100-01-02")              # Sendeplan -> Erscheinungsdatum
                self.assertTrue(all(e["streams"] == [] for s in full["seasons"] for e in s["episodes"]))   # Streams bleiben leer
            plain = metadata.fetch("anilist", 1, with_titles=False, follow=False)
            self.assertEqual(len(plain["seasons"]), 1); self.assertEqual(plain["seasons"][0]["episodes"][0]["title"], "Folge 1")
        finally:
            metadata.HTTP, metadata.SLEEP = old_http, old_sleep

    def test_metadata_import_jikan(self):
        def a(i, title, eps_n, rel=None, typ="TV"):
            return {"mal_id": i, "type": typ, "title": title, "title_english": title + " EN", "title_japanese": title + "JP", "titles": [{"type": "Default", "title": title}],
                    "images": {"jpg": {"large_image_url": f"https://cdn.myanimelist.net/{i}.jpg"}}, "synopsis": "Text &amp; mehr", "episodes": eps_n,
                    "status": "Finished Airing", "year": 2018, "aired": {"from": "2018-01-05T00:00:00+00:00"}, "genres": [{"name": "Comedy"}], "themes": [{"name": "School"}],
                    "relations": rel or []}
        data = {1: a(1, "Jik", 2, [{"relation": "Sequel", "entry": [{"mal_id": 2, "type": "anime"}, {"mal_id": 77, "type": "manga"}]}]), 2: a(2, "Jik2", 1, [{"relation": "Prequel", "entry": [{"mal_id": 1, "type": "anime"}]}])}
        def http(url, payload=None, **kw):
            if "/anime?q=" in url: return {"data": [data[1]]}
            if url.endswith("/full"): return {"data": data[int(url.split("/anime/")[1].split("/")[0])]}
            if "/episodes" in url: return {"data": [{"mal_id": 1, "title": "Pilot", "aired": "2018-01-05"}], "pagination": {"has_next_page": False}}
            raise metadata.MetadataError("x")
        old_http, old_sleep = metadata.HTTP, metadata.SLEEP
        metadata.HTTP, metadata.SLEEP = http, (lambda s: None)
        try:
            self.assertEqual(metadata.search("jikan", "jik")[0]["title"], "Jik EN")
            full = metadata.fetch("jikan", 2)
            self.assertEqual([s["number"] for s in full["seasons"]], [1, 2])
            self.assertEqual(full["seasons"][0]["episodes"][0]["title"], "Pilot"); self.assertEqual(full["genres"], ["Comedy"]); self.assertEqual(full["tags"], ["School"])
            self.assertEqual(full["description"], "Text & mehr")
        finally:
            metadata.HTTP, metadata.SLEEP = old_http, old_sleep

    def test_import_api_permissions_and_errors(self):
        old = metadata.HTTP; metadata.HTTP = self.fake_anilist()
        try:
            self.assertEqual(self.client().get("/api/admin/import/search?q=attack").status_code, 403)
            u = self.user("imp"); self.assertEqual(u.get("/api/admin/import/search?q=attack").status_code, 403)
            r = self.admin.get("/api/admin/import/search?q=attack&provider=anilist"); self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()[0]["id"], 1)
            r = self.admin.get("/api/admin/import/fetch?id=1&provider=anilist&titles=0"); self.assertEqual(len(r.get_json()["seasons"]), 2)
            self.assertEqual(self.admin.get("/api/admin/import/fetch?id=abc").status_code, 400)
            self.assertEqual(self.admin.get("/api/admin/import/search?q=a").status_code, 502)           # zu kurz -> Meldung
            def down(url, payload=None, **kw): raise metadata.MetadataError("Anbieter nicht erreichbar (keine Internetverbindung oder Dienst down).")
            metadata.HTTP = down
            r = self.admin.get("/api/admin/import/search?q=attack"); self.assertEqual(r.status_code, 502); self.assertIn("nicht erreichbar", r.get_json()["error"])
        finally:
            metadata.HTTP = old
        # Importergebnis lässt sich 1:1 speichern (Folgen ohne Stream = angekündigt)
        old = metadata.HTTP; metadata.HTTP = self.fake_anilist()
        try:
            res = self.admin.get("/api/admin/import/fetch?id=1&provider=anilist&titles=0").get_json()
        finally:
            metadata.HTTP = old
        res.update(status="PUBLISHED", bannerUrl=res["bannerUrl"])
        saved = self.admin.post("/api/series", json=res)
        self.assertEqual(saved.status_code, 201, saved.get_data(as_text=True))
        full = saved.get_json()
        self.assertEqual(len(full["seasons"]), 2); self.assertEqual(full["year"], 2020); self.assertEqual(full["alt_titles"][0], "Attack Test romaji")
        self.assertTrue(all(e["status"] == "DRAFT" for s in full["seasons"] for e in s["episodes"]))

    # ============================================================================ Benachrichtigungen
    def setup_subscribers(self, s):
        a = self.user("only_dub"); b = self.user("sub_and_dub"); m = self.user("muted"); d = self.user("custom_sub")
        a.patch("/api/profile/preferences", json={"notifyLangs": ["GERDUB"]})
        b.patch("/api/profile/preferences", json={"notifyLangs": ["GERSUB", "GERDUB"]})
        for c in (a, b, m, d):
            self.assertEqual(c.post("/api/subscriptions", json={"seriesId": s["id"]}).status_code, 201)
        self.assertEqual(m.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "mute"}).status_code, 200)
        self.assertEqual(d.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "custom", "langs": ["GERSUB"]}).status_code, 200)
        return a, b, m, d

    def test_notifications_follow_language_preferences(self):
        s = self.series("Meldeserie", {1: eps(1, [1, 2], langs=("GERSUB",))})
        a, b, m, d = self.setup_subscribers(s)
        for c in (a, b, m, d): self.assertEqual(self.notes(c), [])                  # Abonnieren allein löst nichts aus

        # 1) Staffel 2 erscheint NUR mit Untertiteln
        def add_s2(p): p["seasons"].append({"number": 2, "title": "", "thumbnailUrl": "", "episodes": eps(2, [1, 2], langs=("GERSUB",))})
        s = self.edit(s["id"], add_s2)
        self.assertEqual(self.notes(a), [])                                         # <- nur GerDub: keine Meldung bei Sub-only
        nb = self.notes(b); self.assertEqual([n["type"] for n in nb], ["NEW_SEASON"]); self.assertIn("Staffel 2", nb[0]["message"]); self.assertIn("GerSub", nb[0]["message"])
        self.assertEqual(self.notes(m), [])                                         # stummgeschaltet
        self.assertEqual([n["type"] for n in self.notes(d)], ["NEW_SEASON"])        # eigene Auswahl GerSub

        # 2) Synchro für Staffel 2 kommt dazu
        def add_dub(p):
            for e in p["seasons"][1]["episodes"]:
                e["streams"].append({"lang": "GERDUB", "label": "VOE", "url": f"https://x.example.com/dub/{e['number']}"})
        s = self.edit(s["id"], add_dub)
        na = self.notes(a); self.assertEqual([n["type"] for n in na], ["NEW_SEASON"])
        self.assertIn("Staffel 2", na[0]["message"]); self.assertIn("GerDub", na[0]["message"]); self.assertNotIn("GerSub", na[0]["message"])   # aus Sicht von a ist es eine NEUE Staffel
        self.assertEqual([n["type"] for n in self.notes(b)], ["NEW_LANGUAGE", "NEW_SEASON"])                                                     # b kannte S2 schon -> "weitere Sprache"
        self.assertIn("jetzt auch GerDub", self.notes(b)[0]["message"])
        self.assertEqual([n["type"] for n in self.notes(d)], ["NEW_SEASON"])        # d will nur GerSub -> nichts Neues
        self.assertEqual(self.notes(m), [])

        # 3) Neue Folge in beiden Sprachen
        def add_ep(p): p["seasons"][1]["episodes"] += eps(2, [3], langs=("GERSUB", "GERDUB"))
        s = self.edit(s["id"], add_ep)
        self.assertEqual(self.notes(a)[0]["type"], "NEW_EPISODE"); self.assertIn("Folge in Staffel 2", self.notes(a)[0]["message"])
        self.assertTrue(self.notes(a)[0]["link"].endswith("/s/2/e/3"))                # Link direkt zur Folge
        self.assertIn("GerDub", self.notes(a)[0]["message"]); self.assertNotIn("GerSub", self.notes(a)[0]["message"])
        self.assertEqual(self.notes(b)[0]["type"], "NEW_EPISODE"); self.assertIn("GerDub & GerSub", self.notes(b)[0]["message"])

        # 4) Nichts geändert -> nichts Neues (kein Spam beim erneuten Speichern)
        before = {c.name: len(self.notes(c)) for c in (a, b, d)}
        self.edit(s["id"], lambda p: None)
        self.assertEqual(before, {c.name: len(self.notes(c)) for c in (a, b, d)})
        # Link entfernen und wieder einfügen -> dieselbe Meldung wird nicht doppelt verschickt
        def drop(p): p["seasons"][1]["episodes"][2]["streams"] = [x for x in p["seasons"][1]["episodes"][2]["streams"] if x["lang"] != "GERDUB"]
        s = self.edit(s["id"], drop); s = self.edit(s["id"], lambda p: p["seasons"][1]["episodes"][2]["streams"].append({"lang": "GERDUB", "label": "VOE", "url": "https://x.example.com/2/3/GERDUB"}))
        n_after = len(self.notes(a))
        self.assertLessEqual(n_after, before["only_dub" + str(self.n)] + 1)

    def test_new_language_notice_can_be_switched_off(self):
        s = self.series("Sprachschalter", {1: eps(1, [1], langs=("GERSUB",))})
        u = self.user("nolang")
        u.patch("/api/profile/preferences", json={"notifyLangs": ["GERSUB", "GERDUB"], "notifyNewLangs": False})
        u.post("/api/subscriptions", json={"seriesId": s["id"]})
        self.edit(s["id"], lambda p: p["seasons"][0]["episodes"][0]["streams"].append({"lang": "GERDUB", "label": "VOE", "url": "https://x.example.com/d"}))
        self.assertEqual(self.notes(u), [])
        self.edit(s["id"], lambda p: p["seasons"][0]["episodes"].append(eps(1, [2], langs=("GERSUB",))[0]))
        self.assertEqual([n["type"] for n in self.notes(u)], ["NEW_EPISODE"])      # neue Folgen kommen trotzdem

    def test_notification_pages_and_api(self):
        s = self.series("Glocke", {1: eps(1, [1])})
        u = self.user("bell"); u.post("/api/subscriptions", json={"seriesId": s["id"]})
        self.edit(s["id"], lambda p: p["seasons"][0]["episodes"].append(eps(1, [2])[0]))
        self.assertIn("bell-count\">1<", u.get("/").get_data(as_text=True))          # Zähler an der Glocke
        page = u.get("/notifications").get_data(as_text=True); self.assertIn("Neue Folge", page); self.assertIn("unread", page)
        nid = self.notes(u)[0]["id"]
        r = u.get(f"/notifications/go/{nid}"); self.assertEqual(r.status_code, 302); self.assertIn("/s/1/e/2", r.headers["Location"])   # Klick: weiter + gelesen
        self.assertEqual(u.get("/api/notifications?unread=1").get_json()["unread"], 0)
        self.assertNotIn("bell-count", u.get("/").get_data(as_text=True))
        other = self.user("fremd"); self.assertEqual(other.get(f"/notifications/go/{nid}").status_code, 404)    # nicht fremde Meldungen
        self.assertEqual(u.post("/api/notifications/read", json={}).status_code, 200)
        self.assertEqual(u.delete("/api/notifications", json={}).status_code, 200); self.assertEqual(self.notes(u), [])
        self.assertEqual(self.client().get("/api/notifications").status_code, 401)

    def test_subscription_settings_validation(self):
        s = self.series("Einstellung", {1: eps(1, [1])})
        u = self.user("setu")
        self.assertEqual(u.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "mute"}).status_code, 404)   # nicht abonniert
        u.post("/api/subscriptions", json={"seriesId": s["id"]})
        self.assertEqual(u.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "custom", "langs": []}).status_code, 400)
        self.assertEqual(u.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "custom", "langs": ["XX"]}).status_code, 400)
        self.assertEqual(u.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "nope"}).status_code, 400)
        self.assertEqual(u.patch("/api/subscriptions/settings", json={"seriesId": s["id"], "mode": "custom", "langs": ["GERDUB"]}).status_code, 200)
        self.assertIn('value="GERDUB" checked', u.get(f"/series/{s['slug']}").get_data(as_text=True))
        self.assertEqual(u.patch("/api/profile/preferences", json={"notifyLangs": ["GERDUB", "NOPE"]}).status_code, 400)
        self.assertEqual(u.patch("/api/profile/preferences", json={}).status_code, 400)
        self.assertIn("Benachrichtigungen &amp; Sprache", u.get("/profile").get_data(as_text=True))

    # ============================================================================ Entdecken
    def test_search_by_alternative_title_and_filters(self):
        self.admin.post("/api/series", json=payload("Shingeki Nokyojin", {1: eps(1, [1], langs=("GERDUB",))}, altTitles=["Attack on Titan", "AoT"], year=2013, airStatus="FINISHED", genres=["Action"]))
        self.admin.post("/api/series", json=payload("Anderes Ding", {1: eps(1, [1], langs=("GERSUB",))}, year=2020, airStatus="AIRING", genres=["Comedy"]))
        c = self.client()
        r = c.get("/search?q=attack on titan").get_data(as_text=True)
        self.assertIn("Shingeki Nokyojin", r); self.assertIn("auch: Attack on Titan", r); self.assertNotIn("Anderes Ding", r)    # Zweittitel gefunden
        self.assertIn("Shingeki Nokyojin", c.get("/search?q=AOT").get_data(as_text=True))
        self.assertIn("Shingeki Nokyojin", c.get("/series?q=attack-on titan!").get_data(as_text=True))                       # Satzzeichen egal
        self.assertNotIn("Shingeki", c.get("/series?q=attack&year=2020").get_data(as_text=True))
        self.assertIn("Anderes Ding", c.get("/series?year=2020").get_data(as_text=True))
        self.assertNotIn("Anderes Ding", c.get("/series?year=2013").get_data(as_text=True))
        self.assertIn("Anderes Ding", c.get("/series?status=AIRING").get_data(as_text=True))
        self.assertNotIn("Anderes Ding", c.get("/series?status=FINISHED").get_data(as_text=True))
        self.assertIn("Anderes Ding", c.get("/series?genre=comedy").get_data(as_text=True))
        self.assertNotIn("Anderes Ding", c.get("/series?genre=action").get_data(as_text=True))
        both = c.get("/series?genre=action&lang=GERDUB&year=2013&status=FINISHED").get_data(as_text=True)
        self.assertIn("Shingeki Nokyojin", both); self.assertIn("4 aktiv", both)
        self.assertEqual(c.get("/series?year=abc&status=XX&lang=YY&sort=zzz&page=-4").status_code, 200)                      # kaputte Parameter bremsen nicht

    def test_recently_updated_and_sorting_and_pagination(self):
        s = self.series("Altbestand", {1: eps(1, [1])})
        time.sleep(0.01)
        t = self.series("Frischware", {1: eps(1, [1])})
        with self.app.app_context():
            cards = [c["title"] for c in catalog.search_series({"sort": "updated"})[0]]
            self.assertLess(cards.index("Frischware"), cards.index("Altbestand"))
        self.edit(s["id"], lambda p: p["seasons"][0]["episodes"].append(eps(1, [2], langs=("GERSUB", "GERDUB"))[0]))     # Altbestand bekommt neue Folge
        with self.app.app_context():
            cards = catalog.search_series({"sort": "updated"})[0]
            titles = [c["title"] for c in cards]
            self.assertLess(titles.index("Altbestand"), titles.index("Frischware"))
            self.assertIn("Staffel 1 · Folge 2 (GerDub & GerSub)", [c["note"] for c in cards if c["title"] == "Altbestand"][0])
        home = self.client().get("/").get_data(as_text=True)
        self.assertIn("Zuletzt aktualisiert", home); self.assertIn("Staffel 1 · Folge 2", home)
        with self.app.app_context():
            az = [c["title"] for c in catalog.search_series({"sort": "az"})[0]]
            self.assertEqual(az, sorted(az, key=catalog.norm))
        old = catalog.PAGE_SIZE; catalog.PAGE_SIZE = 2
        try:
            with self.app.app_context():
                _c, total, page, pages = catalog.search_series({"page": "2"})
            self.assertGreater(total, 2); self.assertEqual(page, 2); self.assertEqual(pages, -(-total // 2))
            self.assertIn("Seite 2 von", self.client().get("/series?page=2").get_data(as_text=True))
        finally:
            catalog.PAGE_SIZE = old

    def test_similar_series(self):
        main = self.series("Hauptserie", {1: eps(1, [1])}, genres=["Mecha", "Krimi"], tags=["Zeitreise"], year=2020)
        self.series("PassendEins", {1: eps(1, [1])}, genres=["Mecha"], tags=["Zeitreise"], year=2020)
        self.series("PassendZwei", {1: eps(1, [1])}, genres=["Krimi", "Mecha"])
        self.series("Unpassend", {1: eps(1, [1])}, genres=["Kochen"])
        html = self.client().get(f"/series/{main['slug']}").get_data(as_text=True)
        sim = html[html.index("Ähnliche Serien"):]
        self.assertIn("PassendEins", sim); self.assertIn("PassendZwei", sim); self.assertNotIn("Unpassend", sim)
        self.assertLess(sim.index("PassendZwei"), sim.index("PassendEins"))      # 2 gemeinsame Genres schlagen 1 Genre + Tag + Jahr
        self.assertNotIn(">Hauptserie<", sim)                                    # die Serie selbst taucht nicht auf

    def test_calendar(self):
        today = datetime.now(timezone.utc).date()
        iso = lambda d: d.isoformat()
        self.series("Kalenderserie", {1: [
            {"number": 1, "title": "Alt", "streams": [{"lang": "GERSUB", "label": "x", "url": "https://x.example.com/k1"}], "airedAt": iso(today - timedelta(days=2))},
            {"number": 2, "title": "Heute", "streams": [{"lang": "GERDUB", "label": "x", "url": "https://x.example.com/k2"}, {"lang": "GERSUB", "label": "x", "url": "https://x.example.com/k2s"}], "airedAt": iso(today)},
            {"number": 3, "title": "Bald", "streams": [], "airedAt": iso(today + timedelta(days=3))},
            {"number": 4, "title": "Fern", "streams": [], "airedAt": iso(today + timedelta(days=100))}]})
        html = self.client().get("/calendar").get_data(as_text=True)
        self.assertIn("Erscheinungskalender", html)
        self.assertIn("Heute ·", html); self.assertIn("angekündigt", html)
        up = html[html.index("Demnächst"):html.index("Zuletzt erschienen")]
        self.assertIn("Folge 2", up); self.assertIn("Folge 3", up); self.assertNotIn("Folge 4", html)       # zu weit weg
        self.assertIn("Folge 1", html[html.index("Zuletzt erschienen"):])
        self.assertIn("GerDub", up)
        u = self.user("calu")
        with self.app.app_context():
            sid = db.row("SELECT id FROM series WHERE title='Kalenderserie'")["id"]
        self.assertNotIn("Kalenderserie", u.get("/calendar?mine=1").get_data(as_text=True))                 # noch nicht abonniert
        u.post("/api/subscriptions", json={"seriesId": sid})
        self.assertIn("Kalenderserie", u.get("/calendar?mine=1").get_data(as_text=True))
        self.assertIn("Kalender", self.client().get("/").get_data(as_text=True))
        # Datum-Validierung
        bad = payload("Baddate", {1: [{"number": 1, "title": "x", "streams": [], "airedAt": "morgen"}]})
        self.assertEqual(self.admin.post("/api/series", json=bad).status_code, 400)

    # ============================================================================ Admin-Seiten
    def test_admin_pages_render_with_new_fields(self):
        s = self.series("Editorseite", {1: eps(1, [1])}, altTitles=["Alias"], year=2021, airStatus="AIRING")
        html = self.admin.get(f"/admin/series/{s['id']}/edit").get_data(as_text=True)
        for needle in ("data-import", "altTitles", "Alias", '"airStatus": "AIRING"', '"lang": "GERSUB"', "airedAt"):
            self.assertIn(needle, html.replace("&#34;", '"'))
        self.assertEqual(self.admin.get("/admin/movies/new").status_code, 200)
        self.assertEqual(self.admin.get("/admin/reports").status_code, 200)
        self.assertIn("Gemeldete Streams", self.admin.get("/admin").get_data(as_text=True))
        m = self.admin.post("/api/movies", json={"title": "Filmx", "thumbnailUrl": "https://img.example.com/m.jpg", "status": "PUBLISHED", "altTitles": ["Moviex"], "year": 2019,
                                                 "streams": [{"lang": "OMU", "label": "a", "url": "https://x.example.com/m"}]})
        self.assertEqual(m.status_code, 201); self.assertEqual(m.get_json()["year"], 2019)
        page = self.client().get(f"/movies/{m.get_json()['slug']}").get_data(as_text=True)
        self.assertIn("Moviex", page); self.assertIn("OmU", page)


class MigrationV4(unittest.TestCase):
    def test_old_database_gets_new_columns_and_stream_languages(self):
        path = os.path.join(tempfile.mkdtemp(), "v3.db")
        conn = sqlite3.connect(path)
        schema = (Path(db.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        # Stand vor diesem Funktionspaket: neue Spalten/Tabellen entfernen
        import re
        old = schema
        for col in (r"pref_lang TEXT NOT NULL DEFAULT '',\n", r"notify_langs TEXT NOT NULL DEFAULT '\[\"GERDUB\",\"GERSUB\",\"OMU\"\]',\n", r"notify_new_langs INTEGER NOT NULL DEFAULT 1,\n",
                    r"alt_titles TEXT NOT NULL DEFAULT '\[\]', year INTEGER, air_status TEXT NOT NULL DEFAULT '',\n  content_updated TEXT NOT NULL DEFAULT '', last_update_note TEXT NOT NULL DEFAULT '',\n",
                    r"alt_titles TEXT NOT NULL DEFAULT '\[\]', year INTEGER,\n"):
            old = re.sub(col, "", old, count=1)
        old = old.replace(" aired_at TEXT NOT NULL DEFAULT '',", "").replace("notify_on_new_episode INTEGER NOT NULL DEFAULT 1, notify_langs TEXT,", "notify_on_new_episode INTEGER NOT NULL DEFAULT 1,")
        old = old.replace("is_read INTEGER NOT NULL DEFAULT 0, dedupe_key TEXT NOT NULL DEFAULT '',", "is_read INTEGER NOT NULL DEFAULT 0,")
        old = re.sub(r"CREATE INDEX IF NOT EXISTS idx_notifications_user[^\n]*\n", "", old)
        old = old[:old.index("-- Gemeldete defekte Streams")]
        conn.executescript(old)
        now = "2026-01-01T00:00:00.000Z"
        conn.execute("INSERT INTO users (id,email,password_hash,username,created,updated) VALUES ('u1','a@b.de','x','alt',?,?)", (now, now))
        conn.execute("INSERT INTO series (id,title,slug,thumbnail_url,status,created,updated) VALUES ('s1','Alt','alt','https://i/x.jpg','PUBLISHED',?,?)", (now, now))
        conn.execute("INSERT INTO seasons (id,series_id,number,created,updated) VALUES ('se1','s1',1,?,?)", (now, now))
        conn.execute("""INSERT INTO episodes (id,season_id,number,title,embed_url,embed_provider,streams,status,created,updated)
                        VALUES ('e1','se1',1,'E1','https://old.example.com/1','VOE','[{"label":"VOE","url":"https://old.example.com/1"}]','PUBLISHED',?,?)""", (now, now))
        conn.execute("""INSERT INTO episodes (id,season_id,number,title,embed_url,embed_provider,streams,status,created,updated)
                        VALUES ('e2','se1',2,'E2','https://old.example.com/2','DOOD','[]','PUBLISHED',?,?)""", (now, now))
        conn.commit(); conn.close()
        db.init_db(path); db.init_db(path)                                    # idempotent
        conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row
        self.assertTrue({"alt_titles", "year", "air_status", "content_updated", "last_update_note"} <= {r["name"] for r in conn.execute("PRAGMA table_info(series)")})
        self.assertTrue({"pref_lang", "notify_langs", "notify_new_langs"} <= {r["name"] for r in conn.execute("PRAGMA table_info(users)")})
        self.assertIn("aired_at", {r["name"] for r in conn.execute("PRAGMA table_info(episodes)")})
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"stream_reports", "stream_checks"} <= tables)
        import json
        self.assertEqual(json.loads(conn.execute("SELECT streams FROM episodes WHERE id='e1'").fetchone()[0])[0]["lang"], "OMU")       # Altbestand bekommt Sprache
        e2 = json.loads(conn.execute("SELECT streams FROM episodes WHERE id='e2'").fetchone()[0])
        self.assertEqual((e2[0]["url"], e2[0]["lang"]), ("https://old.example.com/2", "OMU"))                                       # aus embed_url übernommen
        self.assertEqual(conn.execute("SELECT content_updated FROM series WHERE id='s1'").fetchone()[0], now)
        self.assertEqual(json.loads(conn.execute("SELECT notify_langs FROM users WHERE id='u1'").fetchone()[0]), ["GERDUB", "GERSUB", "OMU"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
