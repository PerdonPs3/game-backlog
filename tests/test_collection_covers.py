import sqlite3

import pytest

from app import catalog, create_app
from app.db import get_db


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Cover tests must not make network requests.")
    monkeypatch.setattr(catalog, "urlopen", blocked)


@pytest.fixture
def catalog_cover(app, game_data):
    app.extensions["igdb_client"].get_game.side_effect = None
    app.extensions["igdb_client"].get_game.return_value = {
        "id": 123, "name": "Portal 2", "platforms": [{"name": "PC"}],
        "cover": {"image_id": "co_test"},
    }
    return app.extensions["igdb_client"]


def test_create_persists_trusted_cover_and_collection_uses_it(
    app, client, post_form, game_data, catalog_cover, stored_games
):
    assert post_form("/games/new", {**game_data, "cover_image_id": "https://evil.example"}).status_code == 302
    assert stored_games()[0]["cover_image_id"] == "co_test"
    catalog_cover.reset_mock()
    # Index must not call the API, even if the catalog is offline.
    catalog_cover.get_game.side_effect = catalog.CatalogError("offline")
    for browser in [client, app.test_client()]:
        page = browser.get("/").get_data(as_text=True)
        assert 'src="https://images.igdb.com/igdb/image/upload/t_cover_big/co_test.jpg"' in page
        assert 'loading="lazy"' in page
        assert "evil.example" not in page
    catalog_cover.get_game.assert_not_called()


def test_edit_backfills_cover_for_existing_catalog_game(
    app, client, post_form, game_data, catalog_cover, seed_game, stored_games
):
    game_id = seed_game()
    with app.app_context():
        get_db().execute("UPDATE games SET igdb_id = 123 WHERE id = ?", (game_id,))
        get_db().commit()
    assert stored_games()[0]["cover_image_id"] is None
    assert post_form(f"/games/{game_id}/edit", game_data).status_code == 302
    assert stored_games()[0]["cover_image_id"] == "co_test"
    assert b"t_cover_big/co_test.jpg" in client.get("/").data


def test_invalid_edit_preserves_saved_cover(post_form, game_data, catalog_cover, stored_games):
    assert post_form("/games/new", game_data).status_code == 302
    game = stored_games()[0]
    assert post_form(f"/games/{game['id']}/edit", {**game_data, "rating": "99"}).status_code == 200
    assert stored_games()[0] == game


def test_missing_catalog_cover_has_placeholder(post_form, game_data, client, stored_games):
    assert post_form("/games/new", game_data).status_code == 302
    assert stored_games()[0]["cover_image_id"] is None
    page = client.get("/").get_data(as_text=True)
    assert "No cover available" in page
    assert '<img src=' not in page


@pytest.mark.parametrize("image_id", [None, "../evil", 'x" onerror="alert(1)', "https://evil.example", ""])
def test_stored_invalid_cover_cannot_make_external_url(image_id):
    assert catalog.collection_cover_url(image_id) is None


def test_cover_migration_preserves_catalog_ids_and_legacy_data(tmp_path):
    path = tmp_path / "old-catalog.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, title TEXT, igdb_id INTEGER)")
        connection.execute("INSERT INTO games (title, igdb_id) VALUES ('Portal 2', 123)")
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    with app.app_context():
        row = get_db().execute("SELECT * FROM games").fetchone()
        assert row["title"] == "Portal 2"
        assert row["igdb_id"] == 123
        assert row["cover_image_id"] is None
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM games").fetchone()[0] == 1
