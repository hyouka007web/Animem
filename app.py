"""Startpunkt:  python app.py   (Entwicklung)   |   gunicorn app:app   (Produktion)"""
import os

from animem import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")