from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from app.catalog import CatalogError, game_suggestion, get_catalog
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
    search_query = request.args.get("q", "").strip()

    if status not in ("", "Backlog", "Playing", "Completed"):
        abort(400)

    if len(search_query) > 200:
        abort(400)

    conditions = []
    parameters = []

    if status:
        conditions.append("status = ?")
        parameters.append(status)

    if search_query:
        # Literal substring search: % and _ are not treated as wildcards.
        conditions.append("instr(lower(title), lower(?)) > 0")
        parameters.append(search_query)

    query = "SELECT id, title, platform, status, rating, review FROM games"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC, id DESC"

    games = get_db().execute(query, parameters).fetchall()

    return render_template(
        "index.html",
        games=games,
        selected_status=status,
        search_query=search_query,
    )


@main.get("/catalog/search")
def catalog_search():
    term = request.args.get("q", "").strip()
    if len(term) > 200:
        return jsonify(error="Search must contain no more than 200 characters."), 400
    if len(term) < 2:
        return jsonify(games=[])
    try:
        games = get_catalog().search_games(term)
    except CatalogError:
        return jsonify(error="The catalog is unavailable. Please try again shortly."), 503
    return jsonify(games=[game_suggestion(game) for game in games])


@main.route("/games/new", methods=["GET", "POST"])
def create():
    error = None
    selected_game = None

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

        # Resolve the ID even on validation errors so the dropdown can be restored.
        raw_id = request.form.get("igdb_id", "")
        if raw_id.isascii() and raw_id.isdigit() and len(raw_id) <= 19:
            try:
                catalog_game = get_catalog().get_game(int(raw_id))
                if catalog_game is not None:
                    selected_game = game_suggestion(catalog_game)
            except CatalogError:
                if error is None:
                    error = "The catalog is unavailable. Please try again shortly."
        if error is None:
            if selected_game is None or title != selected_game["name"]:
                error = "Please choose a game from the catalog suggestions."
            elif platform not in selected_game["platforms"]:
                error = "Please choose an available platform for this game."

        if error is None:
            db = get_db()
            db.execute(
                "INSERT INTO games (title, platform, status, rating, review, igdb_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (selected_game["name"], platform, status, rating, review, selected_game["id"]),
            )
            db.commit()

            return redirect(url_for("main.index"))

    return render_template("create.html", error=error, selected_game=selected_game)


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status, rating, review, igdb_id "
        "FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    error = None
    catalog_game = None
    available_platforms = []
    if game["igdb_id"] is not None:
        try:
            catalog_game = get_catalog().get_game(game["igdb_id"])
            if catalog_game is not None:
                available_platforms = game_suggestion(catalog_game)["platforms"]
        except CatalogError:
            error = "The catalog is unavailable. Please try again shortly."
        if catalog_game is None and error is None:
            error = "This game is no longer available in the catalog."

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        platform = request.form.get("platform", "").strip()
        status = request.form.get("status", "")
        error = error or validate_game(title, platform, status)
        if error is None and game["igdb_id"] is not None:
            if title != catalog_game["name"]:
                error = "The title must match the selected catalog game."
            elif platform not in available_platforms:
                error = "Please choose an available platform for this game."

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

    return render_template("edit.html", game=game, error=error,
                           available_platforms=available_platforms)


@main.get("/catalog/games/<int:catalog_id>")
def catalog_game_details(catalog_id):
    try:
        game = get_catalog().get_game(catalog_id)
    except CatalogError:
        return jsonify(error="The catalog is unavailable. Please try again shortly."), 503
    if game is None:
        return jsonify(error="Game not found in the catalog."), 404
    return jsonify(game=game_suggestion(game))


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
