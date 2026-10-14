from flask import Blueprint, abort, redirect, render_template, request, url_for
from app.db import get_db

main = Blueprint("main", __name__)

def validate_game(title, platform, status):
    if not title or len(title) > 200:
        return "Title must contain between 1 and 200 characters."

    if not platform or len(platform) > 80:
        return "Platform must contain between 1 and 80 characters."

    if status not in ("Backlog", "Playing", "Completed"):
        return "Please select a valid status."

    return None


@main.get("/")
def index():
    status = request.args.get("status", "")

    if status not in ("", "Backlog", "Playing", "Completed"):
        abort(400)

    db = get_db()

    if status:
        games = db.execute(
            "SELECT id, title, platform, status, rating, review "
            "FROM games WHERE status = ? "
            "ORDER BY created_at DESC, id DESC",
            (status,),
        ).fetchall()
    else:
        games = db.execute(
            "SELECT id, title, platform, status, rating, review "
            "FROM games ORDER BY created_at DESC, id DESC"
        ).fetchall()

    return render_template(
        "index.html",
        games=games,
        selected_status=status,
    )


@main.route("/games/new", methods=["GET", "POST"])
def create():
    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        platform = request.form.get("platform", "").strip()
        status = request.form.get("status", "")
        error = validate_game(title, platform, status)

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
        error = validate_game(title, platform, status)

        if error is None:
            db.execute(
                "UPDATE games SET title = ?, platform = ?, status = ? "
                "WHERE id = ?",
                (title, platform, status, game_id),
            )
            db.commit()

            return redirect(url_for("main.index"))

    return render_template("edit.html", game=game, error=error)


@main.route("/games/<int:game_id>/delete", methods=["GET", "POST"])
def delete(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    if request.method == "POST":
        db.execute(
            "DELETE FROM games WHERE id = ?",
            (game_id,),
        )
        db.commit()

        return redirect(url_for("main.index"))

    return render_template("delete.html", game=game)