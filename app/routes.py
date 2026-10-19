import json
from random import choice, sample

from flask import Blueprint, abort, flash, jsonify, make_response, redirect, render_template, request, url_for
from app.backups import BACKUP_FIELDS, MAX_BACKUP_BYTES, BackupError, build_backup, parse_backup
from app.catalog import CatalogError, collection_cover_url, cover_image_id, game_profile, game_suggestion, get_catalog
from app.db import DATABASE_ERRORS, INTEGRITY_ERRORS, begin_snapshot, begin_write, get_db, title_contains_sql
from app.game_fields import STATUSES, validate_dates
from app.game_lists import MAX_LISTS, all_lists, clean_list_name, list_cards

main = Blueprint("main", __name__)

DUPLICATE_GAME_ERROR = "This game is already in your collection for this platform."

COLLECTION_SORTS = {
    "newest": ("Recently added", "created_at DESC, id DESC"),
    "oldest": ("Oldest added", "created_at ASC, id ASC"),
    "title": ("Title (A–Z)", "lower(title) ASC, id ASC"),
    "rating": ("Highest rated", "rating IS NULL ASC, rating DESC, created_at DESC, id DESC"),
}


def find_duplicate_game(db, igdb_id, title, platform, exclude_id=None):
    """Prefer catalog identity; compare names only between legacy manual entries."""
    parameters = [platform.strip()]
    conditions = ["lower(trim(platform)) = lower(?)"]
    if igdb_id is not None:
        conditions.append("igdb_id = ?")
        parameters.append(igdb_id)
    else:
        conditions.extend(["igdb_id IS NULL", "lower(trim(title)) = lower(?)"])
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

    if status not in STATUSES:
        return "Please select a valid status."

    return None


def collection_statistics(db):
    """Global entry counts; unrated games do not contribute to the average."""
    row = db.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed, "
        "COALESCE(SUM(CASE WHEN status = 'Playing' THEN 1 ELSE 0 END), 0) AS playing, "
        "COALESCE(SUM(CASE WHEN status = 'Backlog' THEN 1 ELSE 0 END), 0) AS backlog, "
        "COALESCE(SUM(CASE WHEN status = 'On hold' THEN 1 ELSE 0 END), 0) AS on_hold, "
        "COALESCE(SUM(CASE WHEN status = 'Dropped' THEN 1 ELSE 0 END), 0) AS dropped, "
        "COUNT(rating) AS rated, AVG(rating) AS average "
        "FROM games"
    ).fetchone()
    stats = dict(row)
    stats["completion_percent"] = int(stats["completed"] * 100 / stats["total"] + 0.5) if stats["total"] else 0
    return stats


@main.get("/")
def index():
    selected_list = request.args.get("list", "")
    if selected_list:
        if not selected_list.isascii() or not selected_list.isdigit() or len(selected_list) > 18:
            abort(400)
        if get_db().execute("SELECT 1 FROM game_lists WHERE id = ?", (int(selected_list),)).fetchone() is None:
            abort(404)
    status = request.args.get("status", "")
    search_query = request.args.get("q", "").strip()
    selected_sort = request.args.get("sort", "newest")

    if selected_sort not in COLLECTION_SORTS:
        abort(400)

    if status not in ("", *STATUSES):
        abort(400)

    if len(search_query) > 200:
        abort(400)

    conditions = []
    parameters = []
    if selected_list:
        conditions.append("id IN (SELECT game_id FROM game_list_members WHERE list_id = ?)")
        parameters.append(int(selected_list))

    if status:
        conditions.append("status = ?")
        parameters.append(status)

    if search_query:
        # Literal substring search: % and _ are not treated as wildcards.
        conditions.append(title_contains_sql())
        parameters.append(search_query)

    query = "SELECT id, title, platform, status, rating, review, cover_image_id, started_on, completed_on, is_favorite, is_goty FROM games"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    # Only fixed, allowlisted SQL can become an ORDER BY clause.
    query += " ORDER BY " + COLLECTION_SORTS[selected_sort][1]

    games = [
        {**dict(game), "cover_url": collection_cover_url(game["cover_image_id"])}
        for game in get_db().execute(query, parameters).fetchall()
    ]

    context = dict(games=games, selected_status=status, search_query=search_query,
                   selected_sort=selected_sort, sort_options=COLLECTION_SORTS,
                   selected_list=selected_list, lists=all_lists(get_db()))
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


@main.route("/lists", methods=["GET", "POST"])
def lists():
    db = get_db()
    error = None
    if request.method == "POST":
        try:
            name = clean_list_name(request.form.get("name", ""))
        except ValueError as problem:
            error = str(problem)
        else:
            begin_write(db)
            if db.execute("SELECT COUNT(*) FROM game_lists").fetchone()[0] >= MAX_LISTS:
                db.rollback()
                error = "You can create up to 100 lists."
            else:
                try:
                    list_id = db.execute("INSERT INTO game_lists (name, name_key) VALUES (?, ?) RETURNING id", (name, name.casefold())).fetchone()["id"]
                    db.commit()
                    return redirect(url_for("main.edit_list", list_id=list_id))
                except INTEGRITY_ERRORS:
                    db.rollback()
                    error = "A list with this name already exists."
    return render_template("lists.html", lists=list_cards(db), error=error)


@main.route("/lists/<int:list_id>/edit", methods=["GET", "POST"])
def edit_list(list_id):
    db = get_db()
    item = db.execute("SELECT * FROM game_lists WHERE id = ?", (list_id,)).fetchone()
    if item is None:
        abort(404)
    error = None
    view = request.values.get("view", "all")
    if view not in ("all", "selected"):
        view = "all"
    selected = {row[0] for row in db.execute("SELECT game_id FROM game_list_members WHERE list_id = ?", (list_id,))}
    if request.method == "POST":
        try:
            raw_ids = request.form.getlist("games")
            if any(not value.isascii() or not value.isdigit() or len(value) > 18 for value in raw_ids):
                raise ValueError("Please choose games from your collection.")
            selected = {int(value) for value in raw_ids}
            name = clean_list_name(request.form.get("name", ""))
            begin_write(db)
            existing = {row[0] for row in db.execute("SELECT id FROM games")}
            if not selected <= existing:
                raise ValueError("Some selected games are no longer in your collection. Please review your choices.")
            if db.execute("SELECT 1 FROM game_lists WHERE id = ?", (list_id,)).fetchone() is None:
                db.rollback()
                abort(404)
            db.execute("UPDATE game_lists SET name = ?, name_key = ? WHERE id = ?", (name, name.casefold(), list_id))
            db.execute("DELETE FROM game_list_members WHERE list_id = ?", (list_id,))
            db.executemany("INSERT INTO game_list_members (list_id, game_id) VALUES (?, ?)", [(list_id, value) for value in selected])
            db.commit()
            flash("List saved. Your games are right where you left them.", "list_saved")
            return redirect(url_for("main.edit_list", list_id=list_id, view=view, _anchor="list-feedback"))
        except ValueError as problem:
            db.rollback()
            error = str(problem)
        except INTEGRITY_ERRORS:
            db.rollback()
            error = "A list with this name already exists. Your changes were not saved."
    games = [{**dict(row), "cover_url": collection_cover_url(row["cover_image_id"])}
             for row in db.execute("SELECT * FROM games ORDER BY lower(title), platform, id")]
    return render_template("edit_list.html", item=item, games=games, selected=selected, error=error, view=view)


@main.route("/lists/<int:list_id>/delete", methods=["GET", "POST"])
def delete_list(list_id):
    db = get_db()
    item = db.execute("SELECT * FROM game_lists WHERE id = ?", (list_id,)).fetchone()
    if item is None:
        abort(404)
    if request.method == "POST":
        begin_write(db)
        db.execute("DELETE FROM game_lists WHERE id = ?", (list_id,))
        db.commit()
        return redirect(url_for("main.lists"))
    return render_template("delete_list.html", item=item)


@main.get("/games/<int:game_id>")
def game_details(game_id):
    row = get_db().execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        abort(404)
    game = {**dict(row), "cover_url": collection_cover_url(row["cover_image_id"])}
    profile = {"release": None, "genres": [], "summary": None}
    notice = "This entry is not linked to the catalog." if game["igdb_id"] is None else None
    if game["igdb_id"] is not None:
        try:
            catalog_game = get_catalog().get_game(game["igdb_id"])
            if catalog_game is None:
                notice = "Catalog details are no longer available. Your collection entry is safe."
            else:
                profile = game_profile(catalog_game)
        except CatalogError:
            notice = "Catalog details are temporarily unavailable. Your personal notes are still here."
    context = dict(game=game, profile=profile, notice=notice)
    if request.accept_mimetypes.best == "application/json":
        response = jsonify(html=render_template("_game_details.html", **context))
    else:
        response = make_response(render_template("game_details.html", **context))
    response.vary.add("Accept")
    response.headers["Cache-Control"] = "no-store"
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


@main.get("/games/pick")
def pick_game():
    pick_requested = request.args.get("pick") == "1"
    selected_platform = request.args.get("platform", "")
    selected_genre = request.args.get("genre", "")
    if len(selected_platform) > 80 or len(selected_genre) > 100:
        abort(400)
    backlog = get_db().execute("SELECT * FROM games WHERE status = 'Backlog'").fetchall()
    platforms = sorted({row["platform"] for row in backlog}, key=str.casefold)
    if selected_platform and selected_platform not in platforms:
        abort(400)
    genre_map = {}
    error = None
    catalog_ids = {row["igdb_id"] for row in backlog if row["igdb_id"] is not None}
    if catalog_ids:
        try:
            genre_map = get_catalog().get_game_genres(catalog_ids)
        except CatalogError:
            error = "Genre preferences are temporarily unavailable. You can still pick with Any genre."
    genres = sorted({genre for names in genre_map.values() for genre in names}, key=str.casefold)
    if selected_genre and error is None and selected_genre not in genres:
        abort(400)
    candidates = [row for row in backlog
                  if (not selected_platform or row["platform"] == selected_platform)
                  and (not selected_genre or selected_genre in genre_map.get(row["igdb_id"], ()))]
    # A failed genre lookup must never silently suggest a non-matching game.
    if selected_genre and error:
        candidates = []
    game = choice(candidates) if pick_requested and candidates else None
    games = [{**dict(game), "cover_url": collection_cover_url(game["cover_image_id"])}] if game else []
    roulette = None
    if game is not None:
        # The animation is decorative: the fair draw above remains authoritative.
        preview = sample(candidates, min(12, len(candidates)))
        if not any(row["id"] == game["id"] for row in preview):
            preview[0] = game
        roulette = {"winner_id": game["id"], "candidate_count": len(candidates), "games": [
            {"id": row["id"], "title": row["title"],
             "cover_url": collection_cover_url(row["cover_image_id"])} for row in preview
        ]}
    response = make_response(render_template(
        "pick.html", games=games, selected_status="Backlog", search_query="",
        platforms=platforms, genres=genres, selected_platform=selected_platform,
        selected_genre=selected_genre, genre_error=error, has_backlog=bool(backlog),
        candidate_count=len(candidates), pick_requested=pick_requested, roulette=roulette,
    ))
    response.headers["Cache-Control"] = "no-store"
    return response


@main.get("/backups/export")
def export_backup():
    db = get_db()
    # Keep games and membership indices in the same read snapshot.
    begin_snapshot(db)
    rows = db.execute("SELECT * FROM games ORDER BY id").fetchall()
    positions = {row["id"]: index for index, row in enumerate(rows)}
    memberships = {}
    for member in db.execute("SELECT list_id, game_id FROM game_list_members ORDER BY game_id"):
        memberships.setdefault(member["list_id"], []).append(positions[member["game_id"]])
    lists = [{"name": item["name"], "games": memberships.get(item["id"], [])} for item in all_lists(db)]
    db.commit()
    response = make_response(json.dumps(build_backup(rows, lists), ensure_ascii=False, indent=2))
    response.mimetype = "application/json"
    response.headers["Content-Disposition"] = 'attachment; filename="game-backlog-backup.json"'
    response.headers["Cache-Control"] = "no-store"
    return response


@main.route("/backups/import", methods=["GET", "POST"])
def import_backup():
    error = None
    result = None
    if request.method == "POST":
        upload = request.files.get("backup")
        if upload is None or not upload.filename:
            error = "Please choose a JSON backup file."
        elif request.form.get("confirm_import") != "yes":
            error = "Please confirm that you want to add new entries from this backup."
        else:
            try:
                games, backup_lists = parse_backup(upload.read(MAX_BACKUP_BYTES + 1), include_lists=True)
            except BackupError as problem:
                error = str(problem)
            else:
                db = get_db()
                begin_write(db)
                imported = skipped = 0
                try:
                    existing_keys = {row[0] for row in db.execute("SELECT name_key FROM game_lists")}
                    if len(existing_keys | {item["name"].casefold() for item in backup_lists}) > MAX_LISTS:
                        raise ValueError("List limit")
                    saved_ids = []
                    for game in games:
                        duplicate = find_duplicate_game(db, game["igdb_id"], game["title"], game["platform"])
                        if duplicate is not None:
                            skipped += 1
                            saved_ids.append(duplicate["id"])
                            continue
                        cursor = db.execute(
                            "INSERT INTO games (" + ", ".join(BACKUP_FIELDS) + ") "
                            "VALUES (" + ", ".join("?" for _ in BACKUP_FIELDS) + ") RETURNING id",
                            [game[field] for field in BACKUP_FIELDS],
                        )
                        saved_ids.append(cursor.fetchone()["id"])
                        imported += 1
                    for item in backup_lists:
                        db.execute("INSERT INTO game_lists (name, name_key) VALUES (?, ?) ON CONFLICT (name_key) DO NOTHING", (item["name"], item["name"].casefold()))
                        list_id = db.execute("SELECT id FROM game_lists WHERE name_key = ?", (item["name"].casefold(),)).fetchone()[0]
                        db.executemany("INSERT INTO game_list_members (list_id, game_id) VALUES (?, ?) ON CONFLICT (list_id, game_id) DO NOTHING",
                                       [(list_id, saved_ids[index]) for index in item["games"]])
                    db.commit()
                    result = {"imported": imported, "skipped": skipped}
                except DATABASE_ERRORS + (ValueError,):
                    db.rollback()
                    error = "The backup could not be saved. Nothing was imported. Please try again."
    return render_template("import_backup.html", error=error, result=result)


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
        started_on = request.form.get("started_on", "").strip() or None
        completed_on = request.form.get("completed_on", "").strip() or None
        is_favorite = int(request.form.get("is_favorite") == "yes")
        is_goty = int(request.form.get("is_goty") == "yes")
        error = error or validate_dates(started_on, completed_on)

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
            begin_write(db)
            duplicate = find_duplicate_game(
                db, selected_game["id"], selected_game["name"], platform,
            )
            if duplicate is not None:
                duplicate_game_id = duplicate["id"]
                db.rollback()
                error = DUPLICATE_GAME_ERROR
            else:
                db.execute(
                    "INSERT INTO games (title, platform, status, rating, review, igdb_id, cover_image_id, started_on, completed_on, is_favorite, is_goty) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (selected_game["name"], platform, status, rating, review, selected_game["id"],
                     cover_image_id(catalog_game), started_on, completed_on, is_favorite, is_goty),
                )
                db.commit()

                return redirect(url_for("main.index"))

    return render_template("create.html", error=error, selected_game=selected_game,
                           duplicate_game_id=duplicate_game_id)


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status, rating, review, igdb_id, cover_image_id, started_on, completed_on, is_favorite, is_goty "
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
        started_on = request.form.get("started_on", game["started_on"] or "").strip() or None
        completed_on = request.form.get("completed_on", game["completed_on"] or "").strip() or None
        is_favorite = int(request.form.get("is_favorite") == "yes")
        is_goty = int(request.form.get("is_goty") == "yes")
        error = error or validate_dates(started_on, completed_on)
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
            begin_write(db)
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
                    "rating = ?, review = ?, cover_image_id = ?, started_on = ?, completed_on = ?, is_favorite = ?, is_goty = ? "
                    "WHERE id = ?",
                    (title, platform, status, rating, review,
                     cover_image_id(catalog_game) if catalog_game is not None else game["cover_image_id"],
                     started_on, completed_on, is_favorite, is_goty, game_id),
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
        begin_write(db)
        db.execute(
            "DELETE FROM games WHERE id = ?",
            (game_id,),
        )
        db.commit()

        return redirect(url_for("main.index"))

    return render_template("delete.html", game=game)
