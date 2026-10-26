import json
from random import choice, sample

from flask import Blueprint, abort, current_app, flash, g, jsonify, make_response, redirect, render_template, request, url_for
from app.achievements import award_current
from app.wishlist import consume_owned_wishes, wish_state
from app.backups import BACKUP_FIELDS, MAX_BACKUP_BYTES, BackupError, build_backup, parse_backup
from app.catalog import CatalogError, collection_cover_url, cover_image_id, game_profile, game_suggestion, get_catalog
from app.db import DATABASE_ERRORS, INTEGRITY_ERRORS, begin_snapshot, begin_write, get_db, title_contains_sql
from app.game_fields import STATUSES, validate_dates
from app.game_reviews import begin_review_write, can_publish_public_review, save_public_review, validate_public_review
from app.game_lists import MAX_LISTS, all_lists, clean_list_name, list_cards

from app.ownership import owned, member_owned, insert_owned, insert_members

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
    conditions = [owned(), "lower(trim(platform)) = lower(?)"]
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
        f"FROM games WHERE {owned()}"
    ).fetchone()
    stats = dict(row)
    stats["completion_percent"] = int(stats["completed"] * 100 / stats["total"] + 0.5) if stats["total"] else 0
    return stats


@main.get("/")
def welcome():
    # Keep bookmarked filters and older live-filter requests working.
    keys = ("q", "status", "sort", "list")
    if request.accept_mimetypes.best == "application/json" or any(key in request.args for key in keys):
        return redirect(url_for("main.index", **{key: request.args[key] for key in keys if key in request.args}))
    # Public decorative covers, independent of the user's collection and API access.
    image_ids = ("co4jni", "cocpbl", "co1rs4", "cob9kr", "cob9dh", "coaih8", "coaarl", "co1q1f")
    from app.community import member_count
    return render_template("welcome.html", member_count=member_count(), welcome_covers=[collection_cover_url(value) for value in image_ids])


@main.get("/library")
def index():
    selected_list = request.args.get("list", "")
    if selected_list:
        if not selected_list.isascii() or not selected_list.isdigit() or len(selected_list) > 18:
            abort(400)
        if get_db().execute(f"SELECT 1 FROM game_lists WHERE id = ? AND {owned()}", (int(selected_list),)).fetchone() is None:
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

    conditions = [owned()]
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

    query = "SELECT id, title, platform, status, rating, review, igdb_id, cover_image_id, started_on, completed_on, is_favorite, is_goty FROM games"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    # Only fixed, allowlisted SQL can become an ORDER BY clause.
    query += " ORDER BY " + COLLECTION_SORTS[selected_sort][1]

    games = [
        {**dict(game), "cover_url": collection_cover_url(game["cover_image_id"])}
        for game in get_db().execute(query, parameters).fetchall()
    ]

    total = get_db().execute(f"SELECT COUNT(*) FROM games WHERE {owned()}").fetchone()[0] if search_query or status or selected_list else len(games)
    context = dict(games=games, collection_total=total, selected_status=status, search_query=search_query,
                   selected_sort=selected_sort, sort_options=COLLECTION_SORTS,
                   selected_list=selected_list, lists=all_lists(get_db()))
    if request.accept_mimetypes.best == "application/json":
        response = jsonify(
            html=render_template("_game_collection.html", **context), count=len(games), total=total,
        )
    else:
        response = make_response(render_template(
            "index.html", **context,
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
            if db.execute(f"SELECT COUNT(*) FROM game_lists WHERE {owned()}").fetchone()[0] >= MAX_LISTS:
                db.rollback()
                error = "You can create up to 100 lists."
            else:
                try:
                    list_id = insert_owned(db, "game_lists", ("name", "name_key"), (name, name.casefold())).fetchone()["id"]
                    db.commit()
                    return redirect(url_for("main.edit_list", list_id=list_id))
                except INTEGRITY_ERRORS:
                    db.rollback()
                    error = "A list with this name already exists."
    return render_template("lists.html", lists=list_cards(db), error=error)


@main.route("/lists/<int:list_id>/edit", methods=["GET", "POST"])
def edit_list(list_id):
    db = get_db()
    item = db.execute(f"SELECT * FROM game_lists WHERE id = ? AND {owned()}", (list_id,)).fetchone()
    if item is None:
        abort(404)
    error = None
    view = request.values.get("view", "all")
    if view not in ("all", "selected"):
        view = "all"
    selected = {row[0] for row in db.execute(f"SELECT game_id FROM game_list_members WHERE list_id = ? AND {member_owned()}", (list_id,))}
    if request.method == "POST":
        try:
            raw_ids = request.form.getlist("games")
            if any(not value.isascii() or not value.isdigit() or len(value) > 18 for value in raw_ids):
                raise ValueError("Please choose games from your collection.")
            selected = {int(value) for value in raw_ids}
            name = clean_list_name(request.form.get("name", ""))
            begin_write(db)
            existing = {row[0] for row in db.execute(f"SELECT id FROM games WHERE {owned()}")}
            if not selected <= existing:
                raise ValueError("Some selected games are no longer in your collection. Please review your choices.")
            if db.execute(f"SELECT 1 FROM game_lists WHERE id = ? AND {owned()}", (list_id,)).fetchone() is None:
                db.rollback()
                abort(404)
            db.execute(f"UPDATE game_lists SET name = ?, name_key = ? WHERE id = ? AND {owned()}", (name, name.casefold(), list_id))
            db.execute(f"DELETE FROM game_list_members WHERE list_id = ? AND {member_owned()}", (list_id,))
            insert_members(db, [(list_id, value) for value in selected])
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
             for row in db.execute(f"SELECT * FROM games WHERE {owned()} ORDER BY lower(title), platform, id")]
    return render_template("edit_list.html", item=item, games=games, selected=selected, error=error, view=view)


@main.route("/lists/<int:list_id>/delete", methods=["GET", "POST"])
def delete_list(list_id):
    db = get_db()
    item = db.execute(f"SELECT * FROM game_lists WHERE id = ? AND {owned()}", (list_id,)).fetchone()
    if item is None:
        abort(404)
    if request.method == "POST":
        begin_write(db)
        db.execute(f"DELETE FROM game_lists WHERE id = ? AND {owned()}", (list_id,))
        db.commit()
        return redirect(url_for("main.lists"))
    return render_template("delete_list.html", item=item)


@main.get("/games/<int:game_id>")
def game_details(game_id):
    row = get_db().execute(f"SELECT * FROM games WHERE id = ? AND {owned()}", (game_id,)).fetchone()
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
    content = request.args.get("content", "official")
    if content not in ("official", "all"):
        return jsonify(error="Choose a valid catalog filter."), 400
    if len(term) > 200:
        return jsonify(error="Search must contain no more than 200 characters."), 400
    if len(term) < 2:
        return jsonify(games=[])
    try:
        games = get_catalog().search_games(term, include_community=content == "all", suggestions=True)[:10]
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
    backlog = get_db().execute(f"SELECT * FROM games WHERE status = 'Backlog' AND {owned()}").fetchall()
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
    rows = db.execute(f"SELECT * FROM games WHERE {owned()} ORDER BY id").fetchall()
    positions = {row["id"]: index for index, row in enumerate(rows)}
    memberships = {}
    for member in db.execute(f"SELECT list_id, game_id FROM game_list_members WHERE {member_owned()} ORDER BY game_id"):
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
                    existing_keys = {row[0] for row in db.execute(f"SELECT name_key FROM game_lists WHERE {owned()}")}
                    if len(existing_keys | {item["name"].casefold() for item in backup_lists}) > MAX_LISTS:
                        raise ValueError("List limit")
                    saved_ids = []
                    for game in games:
                        duplicate = find_duplicate_game(db, game["igdb_id"], game["title"], game["platform"])
                        if duplicate is not None:
                            skipped += 1
                            saved_ids.append(duplicate["id"])
                            continue
                        cursor = insert_owned(db, "games", BACKUP_FIELDS, [game[field] for field in BACKUP_FIELDS])
                        saved_ids.append(cursor.fetchone()["id"])
                        imported += 1
                    for item in backup_lists:
                        if db.execute(f"SELECT id FROM game_lists WHERE name_key = ? AND {owned()}", (item["name"].casefold(),)).fetchone() is None:
                            insert_owned(db, "game_lists", ("name", "name_key"), (item["name"], item["name"].casefold()))
                        list_id = db.execute(f"SELECT id FROM game_lists WHERE name_key = ? AND {owned()}", (item["name"].casefold(),)).fetchone()[0]
                        insert_members(db,
                                       [(list_id, saved_ids[index]) for index in item["games"]])
                    consume_owned_wishes(db)
                    award_current()
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
    review_publication_available = can_publish_public_review()

    if request.method == 'GET' and 'igdb_id' in request.args:
        raw_id = request.args['igdb_id']
        if not raw_id.isascii() or not raw_id.isdigit() or len(raw_id) > 19 or not 0 < int(raw_id) < 2**63:
            abort(400)
        try:
            catalog_game = get_catalog().get_game(int(raw_id))
            if catalog_game is None:
                abort(404)
            selected_game = game_suggestion(catalog_game)
        except CatalogError:
            error = 'The catalog is unavailable. Please try again shortly.'

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
                error = "Choose a rating from the five-star scale."
            else:
                if not 1 <= rating <= 10:
                    error = "Choose a rating from the five-star scale."

        if error is None and len(review) > 2000:
            error = "Review must contain no more than 2000 characters."
        publish_requested = request.form.get('publish_review') == 'yes'
        if error is None and publish_requested:
            if not review_publication_available:
                error = 'A public profile is required to publish a review.'
            else:
                error = validate_public_review(rating, review)

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
            try:
                begin_write(db)
                duplicate = find_duplicate_game(
                    db, selected_game["id"], selected_game["name"], platform,
                )
                if duplicate is not None:
                    duplicate_game_id = duplicate["id"]
                    db.rollback()
                    error = DUPLICATE_GAME_ERROR
                elif publish_requested:
                    error = begin_review_write(db, publishing=True, in_transaction=True)
                if error is None:
                    insert_owned(
                        db, "games", ("title", "platform", "status", "rating", "review", "igdb_id", "cover_image_id", "started_on", "completed_on", "is_favorite", "is_goty"),
                        (selected_game["name"], platform, status, rating, review, selected_game["id"],
                         cover_image_id(catalog_game), started_on, completed_on, is_favorite, is_goty),
                    )
                    if publish_requested:
                        save_public_review(db, selected_game['id'], rating, review, request.form.get('public_review_spoilers') == 'yes')
                    consume_owned_wishes(db)
                    award_current()
                    db.commit()
            except DATABASE_ERRORS as exc:
                db.rollback()
                current_app.logger.error('Unable to save game and optional public review (%s)', type(exc).__name__)
                error = 'The game could not be saved. Nothing changed. Please try again.'
            if error is None:
                if publish_requested:
                    flash('Added to your library and published your review.', 'catalog_saved')
                    return redirect(url_for('explore.game', catalog_id=selected_game['id'], _anchor='community-reviews'), code=303)
                if request.form.get('return_to_catalog') == 'yes':
                    flash('Added to your library.', 'catalog_saved')
                    return redirect(url_for('explore.game', catalog_id=selected_game['id'], _anchor='library-actions'), code=303)
                return redirect(url_for("main.index"))

    return render_template("create.html", error=error, selected_game=selected_game,
                           duplicate_game_id=duplicate_game_id,
                           review_publication_available=review_publication_available,
                           from_wishlist=bool(selected_game and wish_state(selected_game["id"])))


@main.route("/games/<int:game_id>/edit", methods=["GET", "POST"])
def edit(game_id):
    db = get_db()
    game = db.execute(
        "SELECT id, title, platform, status, rating, review, igdb_id, cover_image_id, started_on, completed_on, is_favorite, is_goty "
        f"FROM games WHERE id = ? AND {owned()}",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    review_publication_available = game['igdb_id'] is not None and can_publish_public_review()
    public_review_spoilers_default = False
    has_public_review = False
    public_review_hidden = False
    if current_app.config.get('AUTH_ENABLED') and game['igdb_id'] is not None:
        shared = db.execute('SELECT has_spoilers, moderation_hidden FROM public_game_reviews WHERE catalog_id = ? AND owner_id = ?',
                            (game['igdb_id'], g.user['id'])).fetchone()
        public_review_spoilers_default = bool(shared and shared[0])
        has_public_review = shared is not None
        public_review_hidden = bool(shared and shared[1])
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
                error = "Choose a rating from the five-star scale."
            else:
                if not 1 <= rating <= 10:
                    error = "Choose a rating from the five-star scale."

        if error is None and len(review) > 2000:
            error = "Review must contain no more than 2000 characters."

        publish_requested = request.form.get('publish_review') == 'yes'
        if error is None and publish_requested:
            if not review_publication_available:
                error = 'A catalog game and public profile are required to publish a review.'
            else:
                error = validate_public_review(rating, review)

        if error is None:
            try:
                begin_write(db)
                current_identity = db.execute(
                    f"SELECT title, platform FROM games WHERE id = ? AND {owned()}", (game_id,),
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
                elif publish_requested:
                    error = begin_review_write(db, publishing=True, in_transaction=True)
                if error is None:
                    db.execute(
                        "UPDATE games SET title = ?, platform = ?, status = ?, "
                        "rating = ?, review = ?, cover_image_id = ?, started_on = ?, completed_on = ?, is_favorite = ?, is_goty = ? "
                        f"WHERE id = ? AND {owned()}",
                        (title, platform, status, rating, review,
                         cover_image_id(catalog_game) if catalog_game is not None else game["cover_image_id"],
                         started_on, completed_on, is_favorite, is_goty, game_id),
                    )
                    if publish_requested:
                        save_public_review(db, game['igdb_id'], rating, review, request.form.get('public_review_spoilers') == 'yes')
                    consume_owned_wishes(db)
                    award_current()
                    db.commit()
            except DATABASE_ERRORS as exc:
                db.rollback()
                current_app.logger.error('Unable to update game and optional public review (%s)', type(exc).__name__)
                error = 'The changes could not be saved. Nothing changed. Please try again.'
            if error is None:
                if publish_requested:
                    flash('Saved your changes and published your review.', 'catalog_saved')
                    return redirect(url_for('explore.game', catalog_id=game['igdb_id'], _anchor='community-reviews'), code=303)
                return redirect(url_for("main.index"))

    return render_template("edit.html", game=game, entry_cover=collection_cover_url(game['cover_image_id']), error=error,
                           available_platforms=available_platforms,
                           duplicate_game_id=duplicate_game_id,
                           review_publication_available=review_publication_available,
                           public_review_spoilers_default=public_review_spoilers_default,
                           has_public_review=has_public_review, public_review_hidden=public_review_hidden)


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
        f"SELECT id, title FROM games WHERE id = ? AND {owned()}",
        (game_id,),
    ).fetchone()

    if game is None:
        abort(404)

    if request.method == "POST":
        begin_write(db)
        db.execute(
            f"DELETE FROM games WHERE id = ? AND {owned()}",
            (game_id,),
        )
        db.commit()

        return redirect(url_for("main.index"))

    return render_template("delete.html", game=game)
