from unittest.mock import Mock
import json
import re

import pytest

from app.catalog import CatalogError, IGDBClient
from app.db import get_db


def set_catalog_id(app, entry_id, catalog_id):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE games SET igdb_id = ? WHERE id = ?", (catalog_id, entry_id))
        db.commit()


def test_platform_only_uses_saved_copy(client, seed_game, stored_games):
    seed_game(title="PC pending", platform="PC", status="Backlog")
    seed_game(title="Console pending", platform="PS3", status="Backlog")
    seed_game(title="PC completed", platform="PC", status="Completed")
    before = stored_games()
    page = client.get("/library/pick?pick=1&platform=PC")
    assert page.status_code == 200
    assert b"PC pending" in page.data
    assert b"Console pending" not in page.data and b"PC completed" not in page.data
    assert b"1 matching entry" in page.data
    assert b'platform=PC&amp;genre=' in page.data
    assert stored_games() == before
    assert page.headers["Cache-Control"] == "no-store"


def test_genre_and_platform_intersection(app, client, seed_game, stored_games):
    puzzle = seed_game(title="Puzzle PC", platform="PC", status="Backlog")
    console = seed_game(title="Puzzle console", platform="PS3", status="Backlog")
    shooter = seed_game(title="Shooter PC", platform="PC", status="Backlog")
    seed_game(title="Manual PC", platform="PC", status="Backlog")
    for entry, catalog_id in [(puzzle, 123), (console, 123), (shooter, 456)]:
        set_catalog_id(app, entry, catalog_id)
    catalog = app.extensions["igdb_client"]
    catalog.get_game_genres.return_value = {123: ("Puzzle", "Adventure"), 456: ("Shooter",)}
    before = stored_games()
    page = client.get("/library/pick", query_string={"pick": "1", "platform": "PC", "genre": "Puzzle"})
    assert page.status_code == 200
    assert b"Puzzle PC" in page.data
    assert b"Puzzle console" not in page.data and b"Shooter PC" not in page.data
    assert b"Manual PC" not in page.data
    assert b'value="Puzzle" selected' in page.data
    assert b"platform=PC&amp;genre=Puzzle" in page.data
    catalog.get_game_genres.assert_called_once_with({123, 456})
    assert stored_games() == before


def test_no_matching_combination_is_not_empty_backlog(app, client, seed_game):
    puzzle = seed_game(title="Puzzle PC", platform="PC", status="Backlog")
    shooter = seed_game(title="Shooter console", platform="PS3", status="Backlog")
    set_catalog_id(app, puzzle, 123)
    set_catalog_id(app, shooter, 456)
    app.extensions["igdb_client"].get_game_genres.return_value = {123: ("Puzzle",), 456: ("Shooter",)}
    page = client.get("/library/pick?pick=1&platform=PS3&genre=Puzzle")
    assert b"No matches this time" in page.data
    assert b"Your Backlog is clear" not in page.data
    assert b"Puzzle PC" not in page.data and b"Shooter console" not in page.data


def test_catalog_failure_never_ignores_selected_genre(app, client, seed_game):
    entry = seed_game(title="Saved adventure", status="Backlog")
    set_catalog_id(app, entry, 123)
    app.extensions["igdb_client"].get_game_genres.side_effect = CatalogError("private token detail")
    page = client.get("/library/pick?pick=1&genre=Puzzle")
    assert page.status_code == 200
    assert b"We could not check this genre" in page.data
    assert b"Saved adventure" not in page.data and b"private token" not in page.data
    assert b"Saved adventure" in client.get("/library/pick?pick=1").data


@pytest.mark.parametrize("query", [
    {"platform": "not in backlog"}, {"genre": "not a genre"},
    {"genre": "x" * 101}, {"platform": "x" * 81},
    {"genre": 'Puzzle; where id > 0;'},
])
def test_invalid_preferences_rejected(client, query):
    assert client.get("/library/pick", query_string=query).status_code == 400


def test_manual_backlog_does_not_require_catalog(app, client, seed_game):
    seed_game(title="Legacy game", status="Backlog")
    catalog = Mock()
    app.extensions["igdb_client"] = catalog
    assert b"Legacy game" in client.get("/library/pick?pick=1").data
    catalog.get_game_genres.assert_not_called()


def test_initial_visit_waits_for_explicit_pick(client, seed_game, monkeypatch, stored_games):
    seed_game(title="Do not reveal me", status="Backlog")
    before = stored_games()
    random_choice = Mock()
    monkeypatch.setattr("app.routes.choice", random_choice)
    for url in ["/library/pick", "/library/pick?platform=PC", "/library/pick?pick=0"]:
        page = client.get(url)
        assert page.status_code == 200
        assert b"What are you in the mood for?" in page.data
        assert b"Do not reveal me" not in page.data
        assert b"No matches this time" not in page.data
        assert b'name="pick" value="1"' in page.data
    random_choice.assert_not_called()
    assert stored_games() == before


def test_genre_batches_are_cached_and_ids_are_validated():
    client = IGDBClient("test", "test")
    client._query_games = Mock(side_effect=lambda query: [
        {"id": 1, "name": "Example", "genres": [{"name": "Puzzle"}]},
        {"id": 9999, "name": "Unexpected", "genres": [{"name": "Shooter"}]},
    ])
    result = client.get_game_genres([*range(1, 202), True, -1, "injection"])
    assert client._query_games.call_count == 2
    assert len(result) == 201 and 9999 not in result
    assert result[1] == ("Puzzle",) and result[201] == ()
    assert "limit 200" in client._query_games.call_args.args[0]
    assert client.get_game_genres([1, 201]) == {1: ("Puzzle",), 201: ()}
    assert client._query_games.call_count == 2
    client._genre_cache[1] = (0, ("Old",))
    assert client.get_game_genres([1]) == {1: ("Puzzle",)}
    assert client._query_games.call_count == 3


def test_failed_genre_batch_is_not_cached_as_empty():
    client = IGDBClient("test", "test")
    client._query_games = Mock(side_effect=CatalogError("Unavailable"))
    with pytest.raises(CatalogError):
        client.get_game_genres([123])
    assert 123 not in client._genre_cache


def test_roulette_only_previews_matching_entries_and_contains_server_winner(app, client, seed_game, monkeypatch):
    for index in range(15):
        seed_game(title=f"Candidate {index}", status="Backlog", platform="PC")
    seed_game(title="Excluded console", status="Backlog", platform="PS3")
    seed_game(title="Excluded completed", status="Completed", platform="PC")
    monkeypatch.setattr("app.routes.choice", lambda rows: rows[-1])
    monkeypatch.setattr("app.routes.sample", lambda rows, count: rows[:count])
    html = client.get("/library/pick?pick=1&platform=PC").get_data(as_text=True)
    data = json.loads(re.search(r'<script id="roulette-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert data["candidate_count"] == 15
    assert len(data["games"]) == 12
    assert data["winner_id"] in [game["id"] for game in data["games"]]
    assert all(game["title"].startswith("Candidate") for game in data["games"])
    assert 'id="adventure-result"' in html
    assert "Skip animation" in html


def test_roulette_json_escapes_html_and_initial_page_does_not_spin(client, seed_game):
    seed_game(title="</script><script>alert(1)</script>", status="Backlog")
    initial = client.get("/library/pick").get_data(as_text=True)
    assert 'id="roulette-data"' not in initial
    result = client.get("/library/pick?pick=1").get_data(as_text=True)
    assert "</script><script>alert(1)</script>" not in result
    assert r"\u003c/script\u003e" in result
