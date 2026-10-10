#!/usr/bin/env python3
"""Verwaltungsbefehle für Animem (ersetzt die alten Node-Skripte).

  python manage.py init-db                       Datenbank anlegen/aktualisieren
  python manage.py make-owner E-MAIL             Konto zum OWNER machen (E-Mail muss zu OWNER_EMAIL passen)
  python manage.py set-role E-MAIL ROLLE         Rolle setzen: USER | ADMIN | HEAD_ADMIN
  python manage.py reset-password E-MAIL         Neues Passwort setzen (ohne alte Anmeldung)
  python manage.py disable-2fa E-MAIL            2FA eines ausgesperrten Kontos abschalten
  python manage.py list-users                    Alle Konten anzeigen
"""
import getpass
import sys

from animem import create_app, db, security


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, args = argv[1], argv[2:]
    app = create_app()
    with app.app_context():
        if cmd == "init-db":
            print(f"Datenbank bereit: {app.config['DB_PATH']}")
            return 0
        if cmd == "list-users":
            for u in db.rows("SELECT username, email, role, is_banned, totp_enabled FROM users ORDER BY created"):
                flags = (" [gesperrt]" if u["is_banned"] else "") + (" [2FA]" if u["totp_enabled"] else "")
                print(f"{u['role']:<11} {u['username']:<20} {u['email']}{flags}")
            return 0
        if not args:
            print("E-Mail fehlt.\n", __doc__)
            return 2
        email = args[0]
        user = db.row("SELECT * FROM users WHERE email=?", (email,))
        if not user:
            print(f"Kein Konto mit der E-Mail {email!r} gefunden. Zuerst normal registrieren.")
            return 1
        if cmd == "make-owner":
            owners = app.config["OWNER_EMAILS"]
            if not owners or email.lower() not in owners:
                print("Abbruch: Die E-Mail muss in OWNER_EMAIL (.env) eingetragen sein, sonst wäre der Owner nicht handlungsfähig.")
                return 1
            db.update("users", user["id"], {"role": "OWNER"})
            print(f"Owner aktiviert: {user['username']} <{user['email']}>")
        elif cmd == "set-role":
            role = args[1] if len(args) > 1 else ""
            if role not in ("USER", "ADMIN", "HEAD_ADMIN"):
                print("Rolle muss USER, ADMIN oder HEAD_ADMIN sein (OWNER nur über make-owner).")
                return 2
            db.update("users", user["id"], {"role": role})
            print(f"{user['username']} ist jetzt {role}.")
        elif cmd == "reset-password":
            pw = getpass.getpass("Neues Passwort (mind. 8 Zeichen): ")
            if len(pw) < 8 or pw != getpass.getpass("Wiederholen: "):
                print("Abbruch: zu kurz oder nicht identisch.")
                return 1
            db.update("users", user["id"], {"password_hash": security.hash_password(pw)})
            db.run("DELETE FROM sessions WHERE user_id=?", (user["id"],))
            print("Passwort geändert, alle Sitzungen beendet.")
        elif cmd == "disable-2fa":
            db.update("users", user["id"], {"totp_enabled": False, "totp_secret": None, "totp_recovery_codes": []})
            print("2FA deaktiviert.")
        else:
            print(f"Unbekannter Befehl: {cmd}\n", __doc__)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
