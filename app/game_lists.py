"""Local, many-to-many lists of collection entries, independent of catalog access."""

MAX_LISTS = 100


def clean_list_name(name):
    if not isinstance(name, str):
        raise ValueError("List name must contain between 1 and 80 characters.")
    name = name.strip()
    if not 1 <= len(name) <= 80 or any(ord(char) < 32 for char in name):
        raise ValueError("List name must contain between 1 and 80 characters, without control characters.")
    return name


def all_lists(db):
    return db.execute(
        "SELECT l.id, l.name, COUNT(m.game_id) AS game_count FROM game_lists l "
        "LEFT JOIN game_list_members m ON m.list_id = l.id "
        "GROUP BY l.id ORDER BY l.name COLLATE NOCASE, l.id"
    ).fetchall()


def list_cards(db):
    from app.catalog import collection_cover_url
    previews = {}
    rows = db.execute(
        "SELECT list_id, cover_image_id FROM ("
        "SELECT m.list_id, g.cover_image_id, ROW_NUMBER() OVER "
        "(PARTITION BY m.list_id ORDER BY g.title COLLATE NOCASE, g.id) AS position "
        "FROM game_list_members m JOIN games g ON g.id = m.game_id) WHERE position <= 4"
    )
    for row in rows:
        previews.setdefault(row["list_id"], []).append(collection_cover_url(row["cover_image_id"]))
    return [{**dict(item), "previews": previews.get(item["id"], [])} for item in all_lists(db)]
