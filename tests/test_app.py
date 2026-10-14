"""Ende-zu-Ende-Tests mit dem Flask-Testclient:  python -m unittest discover -s tests -v"""
import io
import json
import os
import tempfile
import time
import unittest

from animem import create_app, db, security

class _Client:
    """Testclient mit fester Absender-IP (Rate-Limits laufen pro IP)."""
    def __init__(self, app, ip):
        self._c = app.test_client()
        self._ip = ip

    def __getattr__(self, name):
        attr = getattr(self._c, name)
        if name in ("get", "post", "put", "patch", "delete"):
            def call(*a, **kw):
                kw.setdefault("environ_overrides", {})["REMOTE_ADDR"] = self._ip
                return attr(*a, **kw)
            return call
        return attr


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = create_app({
            "DB_PATH": os.path.join(cls.tmp.name, "t.db"), "STORAGE_DIR": os.path.join(cls.tmp.name, "up"),
            "OWNER_EMAILS": ["owner@example.com"], "OWNER_USERNAMES": [], "LINKCHECK_INTERVAL_HOURS": 0,
        })

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    _ip = 0

    def client(self, ip=None):
        Base._ip += 1
        return self.app.test_client(use_cookies=True) if False else _Client(self.app, ip or f"10.1.{Base._ip // 250}.{Base._ip % 250 + 1}")

    def make_user(self, name, role="USER", password="passwort123"):
        with self.app.app_context():
            u = db.insert("users", {"email": f"{name}@example.com", "username": name,
                                    "password_hash": security.hash_password(password), "role": role})
            return u["id"]

    def login(self, c, name, password="passwort123"):
        r = c.post("/api/auth/login", json={"email": f"{name}@example.com", "password": password})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r


SERIES = {
    "title": "Test Serie ÄÖ", "description": "Beschreibung", "thumbnailUrl": "https://img.example.com/a.jpg",
    "bannerUrl": "", "status": "PUBLISHED", "genres": ["Action", "Fantasy"], "tags": ["magie"],
    "seasons": [{"number": 1, "title": "Anfang", "episodes": [
        {"number": 1, "title": "Folge 1", "streams": [{"lang": "GERSUB", "label": "VOE", "url": "https://voe.example.com/e/1"}, {"lang": "GERSUB", "label": "B", "url": "https://b.example.com/1"}]},
        {"number": 2, "title": "Folge 2", "streams": [{"lang": "GERSUB", "label": "VOE", "url": "https://voe.example.com/e/2"}]},
    ]}],
}


class TotpTests(unittest.TestCase):
    def test_rfc6238_vector(self):
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # ASCII "12345678901234567890"
        self.assertEqual(security._hotp(secret, 59 // 30, digits=8), "94287082")
        self.assertEqual(security._hotp(secret, 1111111109 // 30, digits=8), "07081804")
        self.assertTrue(security.verify_totp(secret, security.totp_now(secret)))
        self.assertFalse(security.verify_totp(secret, "000000" if security.totp_now(secret) != "000000" else "111111"))


class PublicPages(Base):
    def test_pages_render(self):
        c = self.client()
        for path in ("/", "/series", "/movies", "/search", "/search?q=x", "/categories", "/login", "/register", "/forum"):
            r = c.get(path)
            self.assertEqual(r.status_code, 200, path)
        self.assertEqual(c.get("/api/health").get_json()["status"], "ok")
        self.assertEqual(c.get("/nope").status_code, 404)
        self.assertEqual(c.get("/api/nope").status_code, 404)
        self.assertIn("Content-Security-Policy", c.get("/").headers)
        self.assertEqual(c.get("/library").status_code, 302)
        self.assertEqual(c.get("/admin").status_code, 302)
        self.assertEqual(c.get("/owner").status_code, 302)
        self.assertEqual(c.get("/api/watchlist").status_code, 401)

    def test_register_login_logout(self):
        c = self.client()
        self.assertEqual(c.post("/api/auth/register", json={"username": "a", "email": "x", "password": "1"}).status_code, 400)
        r = c.post("/api/auth/register", json={"username": "neuer_nutzer", "email": "neu@example.com", "password": "geheim1234"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(c.get("/profile").status_code, 200)
        dup = self.client().post("/api/auth/register", json={"username": "NEUER_NUTZER", "email": "x@example.com", "password": "geheim1234"})
        self.assertEqual(dup.status_code, 400)
        c.delete("/api/auth/session")
        self.assertEqual(c.get("/profile").status_code, 302)
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "neu@example.com", "password": "falsch"}).status_code, 401)
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "neu@example.com", "password": "geheim1234"}).status_code, 200)

    def test_cross_origin_blocked(self):
        r = self.client().post("/api/auth/login", json={}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        r = self.client().post("/api/auth/login", json={}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status_code, 403)


class ContentFlow(Base):
    def test_full_flow(self):
        admin_id = self.make_user("flowadmin", "ADMIN")
        self.make_user("flowuser")
        a, u = self.client(), self.client()
        self.login(a, "flowadmin"); self.login(u, "flowuser")

        # Rechte
        self.assertEqual(u.post("/api/series", json=SERIES).status_code, 403)
        self.assertEqual(u.get("/admin").status_code, 302)

        # Serie anlegen
        r = a.post("/api/series", json=SERIES)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        s = r.get_json()
        self.assertEqual(s["slug"], "test-serie-ao")
        self.assertEqual(len(s["seasons"][0]["episodes"]), 2)
        self.assertEqual(sorted(s["genres"]), ["Action", "Fantasy"])
        bad = dict(SERIES, title="X", thumbnailUrl="http://unsicher.example/a.jpg")
        self.assertEqual(a.post("/api/series", json=bad).status_code, 400)
        bad = json.loads(json.dumps(SERIES)); bad["seasons"][0]["episodes"][0]["streams"][0]["url"] = "javascript:alert(1)"
        self.assertEqual(a.post("/api/series", json=bad).status_code, 400)

        # Seiten
        for path in ("/", "/series", "/series/test-serie-ao", "/series/test-serie-ao/s/1/e/1", "/categories",
                     "/genres/action", "/tags/magie", "/search?q=test"):
            self.assertEqual(u.get(path).status_code, 200, path)
        page = u.get("/series/test-serie-ao/s/1/e/1").get_data(as_text=True)
        self.assertIn("https://voe.example.com/e/1", page)
        self.assertIn("/series/test-serie-ao/s/1/e/2", page)  # nächste Folge
        self.assertEqual(u.get("/series/test-serie-ao/s/9/e/1").status_code, 404)
        self.assertEqual(self.client().get("/series/test-serie-ao").status_code, 200)

        # Umnummerieren (UNIQUE-Konflikt-Test): Folgen tauschen
        full = a.get(f"/api/series/{s['id']}").get_json()
        payload = {"title": full["title"], "description": "neu", "thumbnailUrl": full["thumbnail_url"], "bannerUrl": "",
                   "status": "PUBLISHED", "genres": ["Action"], "tags": [],
                   "seasons": [{"id": full["seasons"][0]["id"], "number": 1, "title": "Anfang", "episodes": [
                       {"id": full["seasons"][0]["episodes"][0]["id"], "number": 2, "title": "Alt-1", "streams": full["seasons"][0]["episodes"][0]["streams"]},
                       {"id": full["seasons"][0]["episodes"][1]["id"], "number": 1, "title": "Alt-2", "streams": full["seasons"][0]["episodes"][1]["streams"]},
                       {"number": 3, "title": "Neu", "streams": [{"lang": "GERSUB", "label": "", "url": "https://n.example.com/3"}]}]}]}
        r = a.patch(f"/api/series/{s['id']}", json=payload)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        eps = {e["number"]: e["title"] for e in r.get_json()["seasons"][0]["episodes"]}
        self.assertEqual(eps, {1: "Alt-2", 2: "Alt-1", 3: "Neu"})
        dup = json.loads(json.dumps(payload)); dup["seasons"][0]["episodes"][2]["number"] = 1
        self.assertEqual(a.patch(f"/api/series/{s['id']}", json=dup).status_code, 400)
        foreign = json.loads(json.dumps(payload)); foreign["seasons"][0]["id"] = "gibtsnicht"
        self.assertEqual(a.patch(f"/api/series/{s['id']}", json=foreign).status_code, 400)
        ep_id = r.get_json()["seasons"][0]["episodes"][0]["id"]

        # Watchlist / Abo / Sammlungen
        sid = s["id"]
        self.assertEqual(u.post("/api/watchlist", json={"seriesId": sid}).status_code, 201)
        self.assertEqual(u.post("/api/watchlist", json={"seriesId": sid}).status_code, 200)  # idempotent
        self.assertEqual(u.post("/api/watchlist", json={"seriesId": sid, "movieId": "x"}).status_code, 400)
        self.assertEqual(len(u.get("/api/watchlist").get_json()), 1)
        self.assertEqual(u.post("/api/subscriptions", json={"seriesId": sid}).status_code, 201)
        col = u.post("/api/collections", json={"title": "Favoriten"}).get_json()
        self.assertEqual(u.post("/api/collections/items", json={"collectionId": col["id"], "seriesId": sid}).status_code, 201)
        self.assertEqual(a.post("/api/collections/items", json={"collectionId": col["id"], "seriesId": sid}).status_code, 404)  # fremde Sammlung
        for tab in ("watchlist", "subscriptions", "history", "watched-episodes", "watched-movies", "collections"):
            self.assertEqual(u.get(f"/library?tab={tab}").status_code, 200, tab)
        self.assertEqual(u.get("/series/test-serie-ao").status_code, 200)
        self.assertEqual(u.delete("/api/watchlist", json={"seriesId": sid}).status_code, 200)

        # Fortschritt -> Verlauf -> gesehen
        u.get(f"/series/test-serie-ao/s/1/e/1")
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep_id}).status_code, 425)  # zu früh
        with self.app.app_context():
            db.run("UPDATE watch_history SET updated=? WHERE episode_id=?", (db.iso_ago(200), ep_id))
        self.assertEqual(u.post("/api/watch/progress", json={"targetType": "EPISODE", "episodeId": ep_id}).status_code, 200)
        self.assertIn("Test Serie", u.get("/library?tab=watched-episodes").get_data(as_text=True))
        self.assertIn("✓", u.get("/series/test-serie-ao").get_data(as_text=True))

        # Bewertungen
        season_id = full["seasons"][0]["id"]
        self.assertEqual(u.post("/api/ratings", json={"targetType": "SERIES", "seriesId": sid, "value": 8}).status_code, 400)  # nur Staffeln
        self.assertEqual(u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": season_id, "value": 8, "comment": "Super @flowadmin"}).status_code, 200)
        self.assertEqual(u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": season_id, "value": 10, "comment": "Noch besser"}).status_code, 200)
        a.post("/api/ratings", json={"targetType": "SEASON", "seasonId": season_id, "value": 6})
        self.assertEqual(u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": season_id, "value": 11}).status_code, 400)
        self.assertEqual(u.post("/api/ratings", json={"targetType": "EPISODE", "seriesId": sid, "value": 5}).status_code, 400)
        with self.app.app_context():
            row = db.row("SELECT avg_rating, ratings_count FROM series WHERE id=?", (sid,))
            srow = db.row("SELECT avg_rating, ratings_count FROM seasons WHERE id=?", (season_id,))
        self.assertEqual((row["avg_rating"], row["ratings_count"]), (8.0, 2))
        self.assertEqual((srow["avg_rating"], srow["ratings_count"]), (8.0, 2))
        revs = u.get(f"/api/ratings?targetType=SEASON&targetId={season_id}").get_json()
        self.assertEqual(len(revs), 1)  # nur Bewertungen mit Kommentar
        self.assertEqual(u.post("/api/ratings", json={"targetType": "EPISODE", "episodeId": ep_id, "value": 7, "comment": "ok"}).status_code, 200)

        # Film
        m = a.post("/api/movies", json={"title": "Film Eins", "thumbnailUrl": "https://img.example.com/m.jpg", "status": "PUBLISHED",
                                        "streams": [{"lang": "GERSUB", "label": "X", "url": "https://x.example.com/m"}], "genres": ["Action"]}).get_json()
        self.assertEqual(u.get("/movies/film-eins").status_code, 200)
        self.assertEqual(a.patch(f"/api/movies/{m['id']}", json={"description": "Neu"}).get_json()["description"], "Neu")
        self.assertEqual(u.post("/api/watchlist", json={"movieId": m["id"]}).status_code, 201)
        self.assertEqual(u.post("/api/profile/favorites", json={"rank": 1, "seriesId": sid}).status_code, 200)
        self.assertEqual(u.post("/api/profile/favorites", json={"rank": 2, "movieId": m["id"]}).status_code, 200)
        self.assertEqual(u.post("/api/profile/favorites", json={"rank": 4, "movieId": m["id"]}).status_code, 400)
        self.assertEqual(u.get("/u/flowuser").status_code, 200)
        self.assertEqual(u.get("/profile").status_code, 200)

        # Entwurf bleibt privat
        d = a.post("/api/series", json=dict(SERIES, title="Geheim", status="DRAFT")).get_json()
        self.assertEqual(u.get("/series/geheim").status_code, 404)
        self.assertEqual(u.post("/api/ratings", json={"targetType": "SEASON", "seasonId": d["seasons"][0]["id"], "value": 5}).status_code, 403)
        self.assertNotIn("Geheim", u.get("/series").get_data(as_text=True))
        self.assertNotIn("Geheim", u.get("/api/series").get_data(as_text=True))
        self.assertEqual(u.get("/api/series?admin=1").status_code, 403)
        self.assertEqual(a.get("/api/series?admin=1").status_code, 200)

        # Admin-Seiten
        for path in ("/admin", "/admin/series", "/admin/series/new", f"/admin/series/{sid}/edit", "/admin/movies",
                     "/admin/movies/new", f"/admin/movies/{m['id']}/edit", "/admin/forum", "/admin/tickets"):
            self.assertEqual(a.get(path).status_code, 200, path)
        self.assertEqual(a.get("/admin/users").status_code, 302)  # nur Head Admin+
        self.assertEqual(a.delete(f"/api/series/{d['id']}").status_code, 403)  # Löschen nur Head Admin+

        # Löschen durch Head Admin
        self.make_user("flowhead", "HEAD_ADMIN"); h = self.client(); self.login(h, "flowhead")
        self.assertEqual(h.delete(f"/api/series/{sid}").status_code, 200)
        self.assertEqual(u.get("/series/test-serie-ao").status_code, 404)
        with self.app.app_context():
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM episodes WHERE season_id NOT IN (SELECT id FROM seasons)"), 0)
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM ratings WHERE series_id=?", (sid,)), 0)
        self.assertEqual(h.get("/admin/users").status_code, 200)

    def test_uploads(self):
        self.make_user("upuser"); c = self.client(); self.login(c, "upuser")
        r = c.post("/api/uploads", data={"file": (io.BytesIO(PNG), "x.png", "image/png")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        url = r.get_json()["url"]
        m = self.client().get(url)
        self.assertEqual((m.status_code, m.mimetype), (200, "image/png"))
        self.assertEqual(c.post("/api/uploads", data={"file": (io.BytesIO(b"GIF8" + b"0" * 20), "x.png", "image/png")}, content_type="multipart/form-data").status_code, 415)
        self.assertEqual(c.post("/api/uploads", data={"file": (io.BytesIO(b"<svg/>"), "x.svg", "image/svg+xml")}, content_type="multipart/form-data").status_code, 415)
        self.assertEqual(self.client().post("/api/uploads", data={"file": (io.BytesIO(PNG), "x.png", "image/png")}, content_type="multipart/form-data").status_code, 401)
        self.assertEqual(c.patch("/api/profile", json={"displayName": "Upper", "bio": "Hi", "avatarUrl": url, "bannerUrl": ""}).status_code, 200)
        self.assertEqual(c.patch("/api/profile", json={"displayName": "x", "bio": "", "avatarUrl": "/etc/passwd", "bannerUrl": ""}).status_code, 400)
        self.make_user("upuser2"); c2 = self.client(); self.login(c2, "upuser2")
        self.assertEqual(c2.patch("/api/profile", json={"displayName": "upper", "bio": "", "avatarUrl": "", "bannerUrl": ""}).status_code, 409)
        self.assertEqual(self.client().get("/api/media/../../etc/passwd").status_code, 404)


class SocialAndSecurity(Base):
    def test_forum_and_tickets(self):
        self.make_user("fuser"); self.make_user("fadmin", "ADMIN")
        u, a = self.client(), self.client(); self.login(u, "fuser"); self.login(a, "fadmin")
        cats = self.client().get("/forum").get_data(as_text=True)
        self.assertIn("Allgemein", cats)
        with self.app.app_context():
            cat = db.row("SELECT * FROM forum_categories WHERE slug='allgemein'")
        r = u.post("/api/forum/threads", json={"categoryId": cat["id"], "title": "Hallo Welt", "content": "Hi @fadmin"})
        self.assertEqual(r.status_code, 201)
        tid = r.get_json()["id"]
        page = self.client().get(f"/forum/allgemein/{tid}").get_data(as_text=True)
        self.assertIn('href="/u/fadmin"', page)
        self.assertEqual(self.client().get(f"/forum/empfehlungen/{tid}").status_code, 404)
        xss = u.post("/api/forum/posts", json={"threadId": tid, "content": "<script>alert(1)</script>"})
        self.assertEqual(xss.status_code, 201)
        self.assertNotIn("<script>alert(1)", self.client().get(f"/forum/allgemein/{tid}").get_data(as_text=True))
        self.assertEqual(u.patch(f"/api/admin/forum/threads/{tid}", json={"isLocked": True}).status_code, 403)
        self.assertEqual(a.patch(f"/api/admin/forum/threads/{tid}", json={"isLocked": True, "isPinned": True}).status_code, 200)
        self.assertEqual(u.post("/api/forum/posts", json={"threadId": tid, "content": "x"}).status_code, 403)
        self.assertEqual(a.post("/api/admin/forum/categories", json={"name": "Neu Kat"}).status_code, 201)
        self.assertEqual(self.client().get("/forum/neu-kat").status_code, 200)

        # Tickets
        t = u.post("/api/tickets", json={"subject": "Problem", "message": "Geht nicht", "priority": "HIGH"})
        self.assertEqual(t.status_code, 201); tk = t.get_json()["id"]
        self.make_user("other"); o = self.client(); self.login(o, "other")
        self.assertEqual(o.get(f"/support/{tk}").status_code, 404)
        self.assertEqual(o.get(f"/api/tickets/{tk}/messages").status_code, 403)
        self.assertEqual(a.get(f"/support/{tk}").status_code, 200)
        self.assertEqual(a.post(f"/api/tickets/{tk}/messages", json={"content": "Wir kümmern uns"}).status_code, 201)
        self.assertEqual(a.patch(f"/api/tickets/{tk}", json={"status": "CLOSED"}).status_code, 200)
        self.assertEqual(u.post(f"/api/tickets/{tk}/messages", json={"content": "x"}).status_code, 403)
        self.assertEqual(u.patch(f"/api/tickets/{tk}", json={"status": "OPEN"}).status_code, 403)
        with self.app.app_context():
            db.run("UPDATE tickets SET updated=? WHERE id=?", (db.iso_ago(90000), tk))
        self.assertEqual(u.get("/support").status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.get("tickets", tk))  # nach 24h geschlossen -> gelöscht

    def test_roles_and_ban(self):
        owner_id = self.make_user("rowner", "OWNER")  # E-Mail rowner@ != owner@example.com -> Identität passt nicht
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "rowner@example.com", "password": "passwort123"}).status_code, 200)
        oc = self.client(); self.login(oc, "rowner")
        self.assertEqual(oc.get("/owner").status_code, 302)  # Owner ohne passende Identität zählt nicht als eingeloggt
        with self.app.app_context():
            db.run("UPDATE users SET email='owner@example.com' WHERE id=?", (owner_id,))
        oc = self.client(); self.assertEqual(oc.post("/api/auth/login", json={"email": "owner@example.com", "password": "passwort123"}).status_code, 200)
        for path in ("/owner", "/owner/database", "/owner/database?table=users", "/owner/audit", "/owner/settings", "/admin/settings", "/admin/users"):
            self.assertEqual(oc.get(path).status_code, 200, path)
        body = oc.get("/owner/database?table=users").get_data(as_text=True)
        self.assertNotIn("password_hash", body); self.assertNotIn("scrypt:", body)

        hid = self.make_user("rhead", "HEAD_ADMIN"); aid = self.make_user("radmin", "ADMIN"); uid = self.make_user("ruser")
        h = self.client(); self.login(h, "rhead"); a = self.client(); self.login(a, "radmin")
        self.assertEqual(h.patch(f"/api/users/{uid}/role", json={"role": "ADMIN"}).status_code, 200)
        self.assertEqual(h.patch(f"/api/users/{uid}/role", json={"role": "HEAD_ADMIN"}).status_code, 403)
        self.assertEqual(h.patch(f"/api/users/{uid}/role", json={"role": "OWNER"}).status_code, 403)
        self.assertEqual(h.patch(f"/api/users/{hid}/role", json={"role": "USER"}).status_code, 403)  # selbst
        self.assertEqual(a.patch(f"/api/users/{uid}/role", json={"role": "USER"}).status_code, 403)
        self.assertEqual(h.patch(f"/api/users/{owner_id}/status", json={"isBanned": True}).status_code, 403)
        # Sperre beendet laufende Sitzungen
        v = self.client(); self.login(v, "ruser")
        self.assertEqual(v.get("/profile").status_code, 200)
        self.assertEqual(h.patch(f"/api/users/{uid}/status", json={"isBanned": True}).status_code, 200)
        self.assertEqual(v.get("/profile").status_code, 302)
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "ruser@example.com", "password": "passwort123"}).status_code, 401)
        with self.app.app_context():
            self.assertGreaterEqual(db.scalar("SELECT COUNT(*) FROM audit_logs"), 2)

        # Einstellungen
        self.assertEqual(h.patch("/api/admin/settings", json={"key": "site_name", "value": "X"}).status_code, 403)
        self.assertEqual(oc.patch("/api/admin/settings", json={"key": "registration_open", "value": False}).status_code, 200)
        self.assertEqual(self.client().post("/api/auth/register", json={"username": "spaet", "email": "s@example.com", "password": "geheim1234"}).status_code, 403)
        oc.patch("/api/admin/settings", json={"key": "registration_open", "value": True})
        self.assertEqual(oc.patch("/api/admin/settings", json={"key": "maintenance_mode", "value": True}).status_code, 200)
        self.assertEqual(self.client().get("/series").status_code, 503)
        self.assertEqual(self.client().get("/login").status_code, 200)
        self.assertEqual(a.get("/series").status_code, 200)  # Team darf rein
        oc.patch("/api/admin/settings", json={"key": "maintenance_mode", "value": False})
        self.assertEqual(self.client().get("/series").status_code, 200)

    def test_totp_flow(self):
        self.make_user("tuser"); c = self.client(); self.login(c, "tuser")
        setup = c.post("/api/profile/totp").get_json()
        self.assertTrue(setup["otpauthUri"].startswith("otpauth://totp/"))
        self.assertEqual(c.patch("/api/profile/totp", json={"code": "000000"}).status_code, 400)
        self.assertEqual(c.patch("/api/profile/totp", json={"code": security.totp_now(setup["secret"])}).status_code, 200)
        self.assertEqual(c.post("/api/profile/totp").status_code, 409)  # keine stille Neu-Einrichtung bei aktiver 2FA

        c2 = self.client()
        r = c2.post("/api/auth/login", json={"email": "tuser@example.com", "password": "passwort123"})
        self.assertTrue(r.get_json()["requiresTotp"])
        self.assertEqual(c2.get("/profile").status_code, 302)  # Pending-Session ist noch kein Login
        self.assertEqual(c2.get("/login?step=totp").status_code, 200)
        self.assertEqual(c2.post("/api/auth/totp", json={"code": "123456"}).status_code, 401)
        self.assertEqual(c2.post("/api/auth/totp", json={"code": security.totp_now(setup["secret"])}).status_code, 200)
        self.assertEqual(c2.get("/profile").status_code, 200)

        # Wiederherstellungscode: einmalig
        c3 = self.client(); c3.post("/api/auth/login", json={"email": "tuser@example.com", "password": "passwort123"})
        code = setup["recoveryCodes"][0]
        r = c3.post("/api/auth/totp", json={"code": code}); self.assertTrue(r.get_json()["usedRecoveryCode"])
        c4 = self.client(); c4.post("/api/auth/login", json={"email": "tuser@example.com", "password": "passwort123"})
        self.assertEqual(c4.post("/api/auth/totp", json={"code": code}).status_code, 401)

        # Sitzungen
        s = c2.get("/api/profile/sessions").get_json()
        self.assertGreaterEqual(len(s), 3); self.assertEqual(sum(1 for x in s if x["current"]), 1)
        self.assertEqual(c2.delete("/api/profile/sessions?all=others").status_code, 200)
        self.assertEqual(c.get("/profile").status_code, 302)  # andere Sitzung beendet
        self.assertEqual(c2.delete("/api/profile/totp", json={"code": "000000"}).status_code, 400)
        self.assertEqual(c2.delete("/api/profile/totp", json={"code": security.totp_now(setup["secret"])}).status_code, 200)

    def test_owner_auto_promote(self):
        os.environ["OWNER_AUTO_PROMOTE"] = "1"
        original = self.app.config["OWNER_EMAILS"]
        self.app.config["OWNER_EMAILS"] = ["promo@example.com"]
        try:
            r = self.client().post("/api/auth/register", json={"username": "fremder", "email": "fremder@example.com", "password": "geheim1234"})
            self.assertEqual(r.get_json()["user"]["role"], "USER")  # falsche E-Mail -> kein Owner
            c = self.client()
            r = c.post("/api/auth/register", json={"username": "echterowner", "email": "promo@example.com", "password": "geheim1234"})
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
            self.assertEqual(r.get_json()["user"]["role"], "OWNER")
            self.assertEqual(c.get("/owner").status_code, 200)
        finally:
            os.environ.pop("OWNER_AUTO_PROMOTE", None)
            self.app.config["OWNER_EMAILS"] = original

    def test_rate_limit(self):
        c = self.client(ip="203.0.113.77")
        codes = [c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"}).status_code for _ in range(10)]
        self.assertEqual(codes[:8], [401] * 8)
        self.assertEqual(codes[8], 429)


if __name__ == "__main__":
    unittest.main()
