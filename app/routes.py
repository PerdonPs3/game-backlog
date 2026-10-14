from flask import Blueprint, render_template
from app.db import get_db

main = Blueprint("main", __name__)


@main.get("/")
def index():
    db = get_db()
    games = db.execute(
        "SELECT id, title, platform, status, rating, review "
        "FROM games ORDER BY created_at DESC, id DESC"
    ).fetchall()

    return render_template("index.html", games=games)