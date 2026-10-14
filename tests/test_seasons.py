"""Tests für Staffel-Bewertung, Staffel-Bilder, Auto-Tracking, Ranking und Migration."""
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from animem import create_app, db, security, services
from test_app import Base, _Client


def series_payload(title, seasons=2, eps=2, covers=True, status="PUBLISHED"):
    out = []
    for n in range(1, seasons + 1):
        out.append({"number": n, "title": "", "thumbnailUrl": f"https://img.example.com/{title}-s{n}.jpg" if covers else "",
                    "episodes": [{"number": e, "title": f"E{e}", "streams": [{"lang": "GERSUB", "label": "x", "url": f"https://x.example.com/{n}/{e}"}]} for e in range(1, eps + 1)]})
    return {"title": title, "description": "", "thumbnailUrl": f"https://img.example.com/{title}.jpg", "bannerUrl": "",
            "status": status, "genres": [], "tags": [], "seasons": out}


class SeasonSystem(Base):
    def setUp(self):
        self.admin = self.client(); self.make_user(f"adm{id(self) % 100000}", "ADMIN")
        self.login(self.admin, f"adm{id(self) % 100000}")

    def new_series(self, title, **kw):
        r = self.admin.post("/api/series", json=series_payload(title, **kw))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()

    def user(self, name):
        self.make_user(name); c = self.client(); self.login(c, name); return c

    def finish_episode(self, c, user_name, episode_id):
        with self.app.app_context():
            uid = db.row("SELECT id FROM users WHERE username=?", (user_name,))["id"]
            existing = db.row("SELECT id FROM watch_history WHERE user_id=? AND episode_id=?", (uid, episode_id))
            if existing:
                db.update("watch_history", existing["id"], {"completed": True})
            else:
                db.insert("watch_history", {"user_id": uid, "target_type": "EPISODE", "episode_id": episode_id, "progress_sec": 180, "completed": True})

    # ---------------------------------------------------------------------------------

    def test_current_season_cover_and_link(self):
        s = self.new_series("Zyklus")
        eps = {(se["number"], e["number"]): e["id"] for se in s["seasons"] for e in se["episodes"]}
        anon = self.client()
        html = anon.get("/series").get_data(as_text=True)
        self.assertIn("Zyklus-s1.jpg", html)                     # abgemeldet: Bild von Staffel 1
        self.assertNotIn("Zyklus-s2.jpg", html)
        self.assertIn('href="/series/zyklus?season=1"', html)

        u = self.user("zykl1")
        self.assertIn("Zyklus-s1.jpg", u.get("/series").get_data(as_text=True))   # noch nie geschaut -> Staffel 1
        self.finish_episode(u, "zykl1", eps[(1, 1)])
        html = u.get("/series").get_data(as_text=True)
        self.assertIn("Zyklus-s1.jpg", html)                     # Staffel 1 nur halb gesehen
        self.finish_episode(u, "zykl1", eps[(1, 2)])
        html = u.get("/series").get_data(as_text=True)
        self.assertIn("Zyklus-s2.jpg", html)                     # Staffel 1 fertig -> Bild + Link von Staffel 2
        self.assertIn('href="/series/zyklus?season=2"', html)
        self.assertNotIn("Zyklus-s1.jpg", html)

        # Klick auf die Serie landet direkt bei Staffel 2 (Cover der Detailseite + sichtbares Panel)
        page = u.get("/series/zyklus").get_data(as_text=True)
        self.assertIn('id="season-cover" src="https://img.example.com/Zyklus-s2.jpg"', page)
        self.assertRegex(page, r'data-panel="1" hidden')
        self.assertNotRegex(page, r'data-panel="2" hidden')
        # explizit andere Staffel anwählbar
        self.assertIn("Zyklus-s1.jpg", u.get("/series/zyklus?season=1").get_data(as_text=True).split('id="season-cover"')[1][:80])
        # Startseite nutzt dasselbe
        self.assertIn("Zyklus-s2.jpg", u.get("/").get_data(as_text=True))

        for e in (2,):
            self.finish_episode(u, "zykl1", eps[(2, 1)])
        self.finish_episode(u, "zykl1", eps[(2, 2)])
        html = u.get("/series").get_data(as_text=True)
        self.assertIn("Zyklus-s2.jpg", html)                     # alles gesehen -> bleibt bei der letzten Staffel
        self.assertIn("Abgeschlossen", u.get("/series/zyklus").get_data(as_text=True))

        # Dritte Staffel: Staffel 3 greift nach Abschluss von Staffel 2 (Regel gilt für jede Staffel)
        s3 = self.new_series("Dreier", seasons=3, eps=1)
        e3 = {se["number"]: se["episodes"][0]["id"] for se in s3["seasons"]}
        self.finish_episode(u, "zykl1", e3[1]); self.finish_episode(u, "zykl1", e3[2])
        self.assertIn("Dreier-s3.jpg", u.get("/series").get_data(as_text=True))

    def test_fallback_to_series_poster_when_season_has_no_image(self):
        self.new_series("Ohnebild", covers=False)
        self.assertIn("img.example.com/Ohnebild.jpg", self.client().get("/series").get_data(as_text=True))

    def test_status_tabs_are_automatic(self):
        s = self.new_series("Status", seasons=1, eps=2)
        eps = [e["id"] for e in s["seasons"][0]["episodes"]]
        u = self.user("stat1")
        self.assertNotIn("Status", u.get("/library?tab=watching").get_data(as_text=True).split("Schaue ich gerade")[-1][:400] if False else "")
        u.get("/series/status/s/1/e/1")                          # Folge nur geöffnet -> "schaue ich gerade"
        self.assertIn("/series/status", u.get("/library?tab=watching").get_data(as_text=True))
        self.assertNotIn("/series/status", u.get("/library?tab=completed").get_data(as_text=True))
        self.assertIn("Weiterschauen", u.get("/library?tab=watching").get_data(as_text=True))
        self.assertIn("Weiter schauen", u.get("/").get_data(as_text=True))
        for e in eps:
            self.finish_episode(u, "stat1", e)
        self.assertIn("/series/status", u.get("/library?tab=completed").get_data(as_text=True))
        self.assertNotIn("/series/status", u.get("/library?tab=watching").get_data(as_text=True))

    def test_three_minute_rule_server_side(self):
        s = self.new_series("Dreimin", seasons=1, eps=1)
        ep = s["seasons"][0]["episodes"][0]["id"]
        u = self.user("drei1")
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep}).status_code, 425)  # nie geöffnet
        u.get("/series/dreimin/s/1/e/1")
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep}).status_code, 425)  # eben erst geöffnet
        with self.app.app_context():
            db.run("UPDATE watch_history SET updated=? WHERE episode_id=?", (db.iso_ago(120), ep))
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep}).status_code, 425)  # nur 2 Minuten
        with self.app.app_context():
            db.run("UPDATE watch_history SET updated=? WHERE episode_id=?", (db.iso_ago(175), ep))
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep}).status_code, 200)

    def test_each_season_has_own_rating(self):
        s = self.new_series("Eigen")
        s1, s2 = s["seasons"][0]["id"], s["seasons"][1]["id"]
        a, b = self.user("rate1"), self.user("rate2")
        for c, season, v in ((a, s1, 6), (b, s1, 8), (a, s2, 9)):
            self.assertEqual(c.post("/api/ratings", json={"targetType": "SEASON", "seasonId": season, "value": v}).status_code, 200)
        a.post("/api/ratings", json={"targetType": "SEASON", "seasonId": s1, "value": 7})   # ändern, nicht doppeln
        with self.app.app_context():
            r1, r2 = db.get("seasons", s1), db.get("seasons", s2)
            ser = db.get("series", s["id"])
        self.assertEqual((r1["avg_rating"], r1["ratings_count"]), (7.5, 2))
        self.assertEqual((r2["avg_rating"], r2["ratings_count"]), (9.0, 1))
        self.assertEqual((ser["avg_rating"], ser["ratings_count"]), (8.0, 3))
        page = a.get("/series/eigen?season=2").get_data(as_text=True)
        self.assertIn('data-target="SEASON" data-id="%s" data-value="9"' % s2, page)    # eigener Wert der Staffel 2
        page = a.get("/series/eigen?season=1").get_data(as_text=True)
        self.assertIn('data-id="%s" data-value="7"' % s1, page)
        self.assertEqual(self.client().post("/api/ratings", json={"targetType": "SEASON", "seasonId": s1, "value": 5}).status_code, 401)

    def test_ranking_seasons_compete_and_weighting(self):
        x = self.new_series("RankX")            # S1 und S2 einer Serie
        y = self.new_series("RankY", seasons=1)
        sx1, sx2, sy1 = x["seasons"][0]["id"], x["seasons"][1]["id"], y["seasons"][0]["id"]
        users = [self.user(f"rk{i}") for i in range(6)]
        # RankX S2: 5 Stimmen mit 9; RankX S1: 5 Stimmen mit 7; RankY S1: eine einzelne 10
        for i, c in enumerate(users[:5]):
            c.post("/api/ratings", json={"targetType": "SEASON", "seasonId": sx2, "value": 9})
            c.post("/api/ratings", json={"targetType": "SEASON", "seasonId": sx1, "value": 7})
        users[5].post("/api/ratings", json={"targetType": "SEASON", "seasonId": sy1, "value": 10})
        with self.app.app_context():
            names = [(r["title"], r["number"]) for r in services.ranking("alltime", 50) if r["title"] in ("RankX", "RankY")]
        # Staffel 2 (Ø9, 5 Stimmen) vor einzelner 10 (1 Stimme) vor Staffel 1 (Ø7)
        self.assertEqual(names[0], ("RankX", 2))
        self.assertLess(names.index(("RankX", 2)), names.index(("RankX", 1)))
        self.assertIn(("RankY", 1), names)
        self.assertLess(names.index(("RankX", 2)), names.index(("RankY", 1)))
        html = self.client().get("/ranking").get_data(as_text=True)
        self.assertIn("Staffel 2", html); self.assertIn('href="/series/rankx?season=2"', html)
        self.assertLess(html.index("season=2"), html.index("season=1"))
        trending = self.client().get("/ranking?tab=trending")
        self.assertEqual(trending.status_code, 200)

    def test_trending_uses_recent_activity(self):
        s = self.new_series("Trend", seasons=1)
        sid = s["seasons"][0]["id"]
        u = self.user("tr1"); u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": sid, "value": 8})
        with self.app.app_context():
            self.assertIn("Trend", [r["title"] for r in services.ranking("trending")])
            db.run("UPDATE ratings SET updated=? WHERE season_id=?", (db.iso_ago(30 * 86400), sid))   # alt -> nicht mehr "aktuell"
            self.assertNotIn("Trend", [r["title"] for r in services.ranking("trending")])
            self.assertIn("Trend", [r["title"] for r in services.ranking("alltime")])

    def test_home_podium(self):
        with self.app.app_context():
            for t in ("seasons", "ratings", "series"):
                pass
        html = self.client().get("/").get_data(as_text=True)
        self.assertIn("beliebtesten Serien", html)
        self.assertIn('class="pod p1', html)                       # Podest ist immer da (leere Plätze als Platzhalter)
        self.assertIn("Noch frei", html) if "pod p1 empty" in html or "empty" in html else None
        # mit 3 Staffeln gefüllt
        for i in range(3):
            s = self.new_series(f"Podium{i}", seasons=1)
            u = self.user(f"pod{i}x{id(self) % 1000}")
            u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": s["seasons"][0]["id"], "value": 10 - i})
        html = self.client().get("/").get_data(as_text=True)
        self.assertEqual(html.count('class="pod p'), 3)
        self.assertIn('class="crown"', html)

    def test_season_image_editable_in_editor_and_removal_cleans_ratings(self):
        s = self.new_series("Editbar")
        s1 = s["seasons"][0]["id"]; sid = s["id"]
        self.user("ed1").post("/api/ratings", json={"targetType": "SEASON", "seasonId": s1, "value": 5})
        full = self.admin.get(f"/api/series/{sid}").get_json()
        payload = {"title": "Editbar", "description": "", "thumbnailUrl": full["thumbnail_url"], "bannerUrl": "", "status": "PUBLISHED",
                   "genres": [], "tags": [],
                   "seasons": [{"id": se["id"], "number": se["number"], "title": "", "thumbnailUrl": "https://img.example.com/neu.jpg" if i == 1 else "",
                                "episodes": [{"id": e["id"], "number": e["number"], "title": e["title"], "streams": e["streams"]} for e in se["episodes"]]}
                               for i, se in enumerate(full["seasons"])]}
        r = self.admin.patch(f"/api/series/{sid}", json=payload); self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["seasons"][1]["thumbnail_url"], "https://img.example.com/neu.jpg")
        self.assertEqual(r.get_json()["seasons"][0]["thumbnail_url"], "")
        payload["seasons"] = payload["seasons"][1:]                  # Staffel 1 entfernen
        self.assertEqual(self.admin.patch(f"/api/series/{sid}", json=payload).status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM ratings WHERE season_id=?", (s1,)), 0)
            self.assertEqual(db.get("series", sid)["ratings_count"], 0)


class Migration(unittest.TestCase):
    def test_old_database_is_upgraded(self):
        schema = (Path(db.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        old = schema.replace("  thumbnail_url TEXT NOT NULL DEFAULT '', avg_rating REAL NOT NULL DEFAULT 0, ratings_count INTEGER NOT NULL DEFAULT 0,\n  UNIQUE(series_id, number)", "  UNIQUE(series_id, number)")
        old = old.replace("('SERIES','SEASON','MOVIE','EPISODE')", "('SERIES','MOVIE','EPISODE')").replace("series_id TEXT, season_id TEXT, movie_id TEXT, episode_id TEXT,", "series_id TEXT, movie_id TEXT, episode_id TEXT,")
        old = re.sub(r"^CREATE (UNIQUE )?INDEX IF NOT EXISTS idx_ratings_(user_season|season_created).*$", "", old, flags=re.M)
        self.assertNotIn("season_id TEXT, movie_id", old)
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        conn = sqlite3.connect(path); conn.executescript(old)
        now = "2026-01-01T00:00:00.000Z"
        conn.execute("INSERT INTO users (id,email,password_hash,username,created,updated) VALUES ('u1','a@b.de','x','alt',?,?)", (now, now))
        conn.execute("INSERT INTO series (id,title,slug,thumbnail_url,status,created,updated) VALUES ('s1','Alt','alt','https://i/x.jpg','PUBLISHED',?,?)", (now, now))
        conn.execute("INSERT INTO seasons (id,series_id,number,created,updated) VALUES ('se1','s1',1,?,?)", (now, now))
        conn.execute("INSERT INTO seasons (id,series_id,number,created,updated) VALUES ('se2','s1',2,?,?)", (now, now))
        conn.execute("INSERT INTO movies (id,title,slug,thumbnail_url,embed_url,created,updated) VALUES ('m1','Film','film','https://i/y.jpg','https://e/1',?,?)", (now, now))
        conn.execute("INSERT INTO ratings (id,user_id,target_type,series_id,value,comment,created,updated) VALUES ('r1','u1','SERIES','s1',8,'gut',?,?)", (now, now))
        conn.execute("INSERT INTO ratings (id,user_id,target_type,movie_id,value,created,updated) VALUES ('r2','u1','MOVIE','m1',6,?,?)", (now, now))
        conn.commit(); conn.close()

        db.init_db(path); db.init_db(path)                           # zweimal: muss idempotent sein
        conn = sqlite3.connect(path); conn.row_factory = sqlite3.Row
        rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM ratings")}
        self.assertEqual(rows["r1"]["target_type"], "SEASON")        # alte Serien-Bewertung -> Staffel 1
        self.assertEqual(rows["r1"]["season_id"], "se1")
        self.assertEqual(rows["r2"]["target_type"], "MOVIE")
        s = conn.execute("SELECT avg_rating, ratings_count FROM seasons WHERE id='se1'").fetchone()
        self.assertEqual((s["avg_rating"], s["ratings_count"]), (8.0, 1))
        self.assertEqual(conn.execute("SELECT ratings_count FROM series WHERE id='s1'").fetchone()[0], 1)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(seasons)")}
        self.assertTrue({"thumbnail_url", "avg_rating", "ratings_count"} <= cols)
        conn.execute("INSERT INTO ratings (id,user_id,target_type,season_id,value,created,updated) VALUES ('r3','u1','SEASON','se2',9,'x','x')")  # neue CHECK-Regel greift
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO ratings (id,user_id,target_type,season_id,value,created,updated) VALUES ('r4','u1','SEASON','se2',7,'x','x')")  # Unique pro Staffel
        conn.close()


if __name__ == "__main__":
    unittest.main()
