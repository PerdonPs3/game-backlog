from flask import Blueprint, abort, redirect, render_template, request, url_for
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


@main.route("/games/new", methods=["GET", "POST"])
def create():
    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        platform = request.form.get("platform", "").strip()
        status = request.form.get("status", "")

        if not title or len(title) > 200:
            error = "Title must contain between 1 and 200 characters."
        elif not platform or len(platform) > 80:
            error = "Platform must contain between 1 and 80 characters."
        elif status not in ("Backlog", "Playing", "Completed"):
            error = "Please select a valid status."

        if error is None:
            db = get_db()
            db.execute(
                "INSERT INTO games (title, platform, status) VALUES (?, ?, ?)",
                (title, platform, status),
            )
            db.commit()

            return redirect(url_for("main.index"))

    return render_template("create.html", error=error)


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        platform = request.form.get("platform", "").strip()
        status = request.form.get("status", "")

        if not title or len(title) > 200:
            error = "Title must contain between 1 and 200 characters."
        elif not platform or len(platform) > 80:
            error = "Platform must contain between 1 and 80 characters."
        elif status not in ("Backlog", "Playing", "Completed"):
            error = "Please select a valid status."

        if error is None:
            db.execute(
                "UPDATE games SET title = ?, platform = ?, status = ? "
                "WHERE id = ?",
                (title, platform, status, game_id),
            )
            db.commit()

            return redirect(url_for("main.index"))

    return render_template("edit.html", game=game, error=error)