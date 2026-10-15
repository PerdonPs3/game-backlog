from flask import Blueprint, abort, jsonify, make_response, redirect, render_template, request, url_for
from app.catalog import CatalogError, collection_cover_url, cover_image_id, game_suggestion, get_catalog
from app.db import get_db

main = Blueprint("main", __name__)

DUPLICATE_GAME_ERROR = "This game is already in your collection for this platform."

COLLECTION_SORTS = {
    "newest": ("Recently added", "created_at DESC, id DESC"),
    "oldest": ("Oldest added", "created_at ASC, id ASC"),
    "title": ("Title (A–Z)", "title COLLATE NOCASE ASC, id ASC"),
    "rating": ("Highest rated", "rating IS NULL ASC, rating DESC, created_at DESC, id DESC"),
}


def find_duplicate_game(db, igdb_id, title, platform, exclude_id=None):
    """Prefer catalog identity; compare names only between legacy manual entries."""
    parameters = [platform.strip()]
    conditions = ["trim(platform) = ? COLLATE NOCASE"]
    if igdb_id is not None:
        conditions.append("igdb_id = ?")
        parameters.append(igdb_id)
    else:
        conditions.extend(["igdb_id IS NULL", "trim(title) = ? COLLATE NOCASE"])
        parameters.append(title.strip())
    if exclude_id is not None:
        conditions.append("id != ?")
        parameters.append(exclude_id)
    return db.execute(
        "SELECT id FROM games WHERE " + " AND ".join(conditions) + " ORDER BY id LIMIT 1",
        parameters,
    ).fetchone()


def validate_game(title, platform, status):
    if not title or len(title) > 200:
        return "Title must contain between 1 and 200 characters."

    if not platform or len(platform) > 80:
        return "Platform must contain between 1 and 80 characters."

    if status not in ("Backlog", "Playing", "Completed"):
        return "Please select a valid status."

    return None


def collection_statistics(db):
    """Global entry counts; unrated games do not contribute to the average."""
    row = db.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(status = 'Completed'), 0) AS completed, "
        "COALESCE(SUM(status = 'Playing'), 0) AS playing, "
        "COALESCE(SUM(status = 'Backlog'), 0) AS backlog, "
        "COUNT(rating) AS rated, AVG(rating) AS average "
        "FROM games"
    ).fetchone()
    stats = dict(row)
    stats["completion_percent"] = int(stats["completed"] * 100 / stats["total"] + 0.5) if stats["total"] else 0
    return stats


@main.get("/")
def index():
    status = request.args.get("status", "")
    search_query = request.args.get("q", "").strip()
    selected_sort = request.args.get("sort", "newest")

    if selected_sort not in COLLECTION_SORTS:
        abort(400)

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

    query = "SELECT id, title, platform, status, rating, review, cover_image_id FROM games"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    # Only fixed, allowlisted SQL can become an ORDER BY clause.
    query += " ORDER BY " + COLLECTION_SORTS[selected_sort][1]

    games = [
        {**dict(game), "cover_url": collection_cover_url(game["cover_image_id"])}
        for game in get_db().execute(query, parameters).fetchall()
    ]

    context = dict(games=games, selected_status=status, search_query=search_query,
                   selected_sort=selected_sort, sort_options=COLLECTION_SORTS)
    if request.accept_mimetypes.best == "application/json":
        response = jsonify(
            html=render_template("_game_collection.html", **context), count=len(games),
        )
    else:
        response = make_response(render_template(
            "index.html", stats=collection_statistics(get_db()), **context,
        ))
    response.vary.add("Accept")
    return response


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
    duplicate_game_id = None

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
            # Serialize check + write so simultaneous submissions cannot both pass.
            db.execute("BEGIN IMMEDIATE")
            duplicate = find_duplicate_game(
                db, selected_game["id"], selected_game["name"], platform,
            )
            if duplicate is not None:
                duplicate_game_id = duplicate["id"]
                db.rollback()
                error = DUPLICATE_GAME_ERROR
            else:
                db.execute(
                    "INSERT INTO games (title, platform, status, rating, review, igdb_id, cover_image_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (selected_game["name"], platform, status, rating, review, selected_game["id"],
                     cover_image_id(catalog_game)),
                )
                db.commit()

                return redirect(url_for("main.index"))

    return render_template("create.html", error=error, selected_game=selected_game,
                           duplicate_game_id=duplicate_game_id)


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status, rating, review, igdb_id, cover_image_id "
        "FROM games WHERE id = ?",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    error = None
    duplicate_game_id = None
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
            db.execute("BEGIN IMMEDIATE")
            current_identity = db.execute(
                "SELECT title, platform FROM games WHERE id = ?", (game_id,),
            ).fetchone()
            if current_identity is None:
                db.rollback()
                abort(404)
            identity_changed = (
                platform.casefold() != current_identity["platform"].strip().casefold()
                or (game["igdb_id"] is None and title.casefold() != current_identity["title"].strip().casefold())
            )
            # Pre-existing duplicates remain editable; never delete or merge user data.
            duplicate = find_duplicate_game(db, game["igdb_id"], title, platform, game_id) if identity_changed else None
            if duplicate is not None:
                duplicate_game_id = duplicate["id"]
                db.rollback()
                error = DUPLICATE_GAME_ERROR
            else:
                db.execute(
                    "UPDATE games SET title = ?, platform = ?, status = ?, "
                    "rating = ?, review = ?, cover_image_id = ? "
                    "WHERE id = ?",
                    (title, platform, status, rating, review,
                     cover_image_id(catalog_game) if catalog_game is not None else game["cover_image_id"],
                     game_id),
                )
                db.commit()

                return redirect(url_for("main.index"))

    return render_template("edit.html", game=game, error=error,
                           available_platforms=available_platforms,
                           duplicate_game_id=duplicate_game_id)


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
