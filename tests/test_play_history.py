import sqlite3

import pytest

from app import create_app
from app.db import get_db
from app.routes import collection_statistics


@pytest.mark.parametrize("status", ["On hold", "Dropped"])
def test_new_status_is_saved_filtered_and_counted(app, client, post_form, game_data, stored_games, status):
    assert post_form("/library/add", {**game_data, "status": status}).status_code == 302
    assert stored_games()[0]["status"] == status
    assert b"Portal 2" in client.get("/library", query_string={"status": status}).data
    assert client.get("/library", query_string={"status": status}, headers={"Accept": "application/json"}).json["count"] == 1
    with app.app_context():
        stats = collection_statistics(get_db())
    assert stats["on_hold" if status == "On hold" else "dropped"] == 1


def test_dates_can_be_created_displayed_edited_and_cleared(client, post_form, game_data, stored_games):
    dates = {"started_on": "2026-01-01", "completed_on": "2026-02-05"}
    assert post_form("/library/add", {**game_data, **dates, "status": "Completed"}).status_code == 302
    game = stored_games()[0]
    assert game["started_on"] == dates["started_on"]
    assert game["completed_on"] == dates["completed_on"]
    assert b'<time datetime="2026-02-05">' in client.get("/library").data
    url = f"/library/entries/{game['id']}/edit"
    assert b'value="2026-01-01"' in client.get(url).data
    assert post_form(url, {**game_data, "started_on": "", "completed_on": ""}).status_code == 302
    assert stored_games()[0]["started_on"] is None
    assert stored_games()[0]["completed_on"] is None


@pytest.mark.parametrize("dates", [
    {"started_on": "not-a-date"}, {"started_on": "2026-02-30"},
    {"started_on": "20260101"}, {"completed_on": "x" * 200},
    {"started_on": "2026-02-01", "completed_on": "2026-01-01"},
])
def test_invalid_dates_preserve_existing_data(post_form, game_data, stored_games, dates):
    assert post_form("/library/add", {**game_data, **dates}).status_code == 200
    assert stored_games() == []
    assert post_form("/library/add", game_data).status_code == 302
    before = stored_games()
    assert post_form(f"/library/entries/{before[0]['id']}/edit", {**game_data, **dates}).status_code == 200
    assert stored_games() == before


def test_status_changes_do_not_invent_dates(post_form, game_data, stored_games):
    assert post_form("/library/add", {**game_data, "status": "Completed"}).status_code == 302
    assert stored_games()[0]["started_on"] is None
    assert stored_games()[0]["completed_on"] is None


def test_status_migration_preserves_data_and_original_snapshot(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE games (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, platform TEXT NOT NULL,
            status TEXT CHECK(status IN ('Backlog','Playing','Completed')),
            rating INTEGER, review TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("INSERT INTO games (id,title,platform,status,rating,review) VALUES (9,'Original','PC','Playing',8,'Keep this')")
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT * FROM games WHERE id=9").fetchone()
        assert row["review"] == "Keep this"
        assert row["rating"] == 8
        assert row["started_on"] is None
        assert db.execute("SELECT title FROM games_before_status_upgrade WHERE id=9").fetchone()[0] == "Original"
        db.execute("UPDATE games SET status='On hold' WHERE id=9")
        db.commit()
    with app.app_context():
        assert get_db().execute("SELECT status FROM games WHERE id=9").fetchone()[0] == "On hold"


def test_random_pick_only_chooses_backlog_and_never_changes_status(client, seed_game, stored_games):
    seed_game(title="Pending adventure", status="Backlog")
    for status in ["Completed", "Playing", "On hold", "Dropped"]:
        seed_game(title=f"Exclude {status}", status=status)
    before = stored_games()
    page = client.get("/library/pick?pick=1")
    assert page.status_code == 200
    assert b"Pending adventure" in page.data
    assert b"Exclude" not in page.data
    assert stored_games() == before


def test_random_pick_has_help_when_no_backlog(client):
    page = client.get("/library/pick")
    assert page.status_code == 200
    assert b"No pending games yet" in page.data


def test_failed_status_migration_rolls_back_every_change(tmp_path):
    path = tmp_path / "invalid-old.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE games (
            id INTEGER PRIMARY KEY, title TEXT, platform TEXT, status TEXT,
            rating INTEGER, review TEXT, created_at TEXT
        )""")
        # Invalid legacy data must never be discarded to force a migration through.
        db.execute("INSERT INTO games VALUES (1,'Original','PC','Playing',99,'Keep me','2026-01-01')")
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    with app.app_context(), pytest.raises(sqlite3.IntegrityError):
        get_db()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT review FROM games").fetchone()[0] == "Keep me"
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='games_status_upgrade'").fetchone()[0] == 0
        assert "started_on" not in {row[1] for row in db.execute("PRAGMA table_info(games)")}
