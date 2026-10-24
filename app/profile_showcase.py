"""Private, ordered game showcases with database-enforced ownership and limits."""

from app.catalog import collection_cover_url


MAX_SHOWCASE_GAMES = 5


def game_cards(rows):
    return [{**dict(row), "cover_url": collection_cover_url(row["cover_image_id"])} for row in rows]


def showcase_games(db, user_id):
    return game_cards(db.execute(
        "SELECT g.id, g.title, g.platform, g.status, g.rating, g.cover_image_id, s.position "
        "FROM profile_showcase s JOIN games g ON g.id = s.game_id AND g.owner_id = s.owner_id "
        "WHERE s.owner_id = ? ORDER BY s.position", (user_id,)
    ).fetchall())


def save_showcase(db, user_id, values):
    choices = [value for value in values if value]
    if len(values) > MAX_SHOWCASE_GAMES or len(choices) != len(set(choices)):
        raise ValueError("Choose up to five different games. Each game can appear only once.")
    if any(not value.isascii() or not value.isdigit() or len(value) > 18 or int(value) < 1 for value in choices):
        raise ValueError("Choose games from your own library.")
    ids = [int(value) for value in choices]
    if len(set(ids)) != len(ids):
        raise ValueError("Choose up to five different games. Each game can appear only once.")
    db.execute("BEGIN")
    try:
        # Serialize replacements for this account; FK checks also enforce ownership.
        db.execute("SELECT id FROM profiles WHERE id = ? FOR UPDATE", (user_id,))
        if ids:
            placeholders = ", ".join("?" for _ in ids)
            games = db.execute(f"SELECT id FROM games WHERE owner_id = ? AND id IN ({placeholders}) FOR KEY SHARE", (user_id, *ids)).fetchall()
            if len(games) != len(ids):
                raise ValueError("Choose games from your own library. A game may have been removed.")
        db.execute("DELETE FROM profile_showcase WHERE owner_id = ?", (user_id,))
        if ids:
            db.executemany("INSERT INTO profile_showcase (owner_id, position, game_id) VALUES (?, ?, ?)",
                           [(user_id, position, game_id) for position, game_id in enumerate(ids, 1)])
        db.commit()
    except Exception:
        db.rollback()
        raise
