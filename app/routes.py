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
        rating_text = request.form.get("rating", "").strip()
        review = request.form.get("review", "").strip()
        error = validate_game(title, platform, status)

        rating = None

        if error is None and rating_text:
            try:
                rating = int(rating_text)
            except ValueError:
                error = "Rating must be a whole number between 1 and 10."
            else:
                if not 1 <= rating <= 10:
                    error = "Rating must be a whole number between 1 and 10."

        if error is None and len(review) > 2000:
            error = "Review must contain no more than 2000 characters."

        if error is None:
            db = get_db()
            db.execute(
                "INSERT INTO games (title, platform, status, rating, review) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, platform, status, rating, review),
            )
            db.commit()

            return redirect(url_for("main.index"))

    return render_template("create.html", error=error)


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status, rating, review "
        "FROM games WHERE id = ?",
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

        rating_text = request.form.get("rating", "").strip()
        review = request.form.get("review", "").strip()
        rating = None

        if error is None and rating_text:
            try:
                rating = int(rating_text)
            except ValueError:
                error = "Rating must be a whole number between 1 and 10."
            else:
                if not 1 <= rating <= 10:
                    error = "Rating must be a whole number between 1 and 10."

        if error is None and len(review) > 2000:
            error = "Review must contain no more than 2000 characters."

        if error is None:
            db.execute(
                "UPDATE games SET title = ?, platform = ?, status = ?, "
                "rating = ?, review = ? "
                "WHERE id = ?",
                (title, platform, status, rating, review, game_id),
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
