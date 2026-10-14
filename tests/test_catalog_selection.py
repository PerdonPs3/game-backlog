import sqlite3
from unittest.mock import Mock

import pytest

from app import catalog, create_app
from app.db import get_db


@pytest.fixture(autouse=True)
def no_catalog_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not use real catalog credentials or network.")
    monkeypatch.setattr(catalog, "urlopen", blocked)


def test_search_filters_versions_ports_and_duplicate_ids(monkeypatch):
    original = {"id": 1, "name": "Resident Evil", "first_release_date": 828316800}
    remake = {"id": 2, "name": "Resident Evil", "game_type": {"type": "Remake"}}
    version = {"id": 3, "name": "Resident Evil", "version_parent": 1}
    port = {"id": 4, "name": "Resident Evil", "game_type": {"type": "Port"}}
    request = Mock(side_effect=[
        {"access_token": "test", "expires_in": 3600},
        [original, original, remake, version, port],
    ])
    monkeypatch.setattr(catalog, "_request_json", request)
    client = catalog.IGDBClient("fake", "fake")
    assert client.search_games("Resident") == [original, remake]
    query = request.call_args.args[0].data.decode()
    assert "version_parent = null" in query
    assert '"Port"' in query


def test_platforms_include_linked_ports_without_duplicates():
    game = {"id": 1, "name": "Game", "platforms": [{"name": "PC"}],
            "ports": [{"platforms": [{"name": "PC"}, {"name": "PlayStation"}]}]}
    assert catalog.game_suggestion(game)["platforms"] == ["PC", "PlayStation"]


def test_search_sorts_by_full_release_date_newest_first(monkeypatch):
    games = [
        {"id": 1, "name": "FC 25", "first_release_date": 1727395200},
        {"id": 2, "name": "FC 27", "first_release_date": 1790294400},
        {"id": 3, "name": "FC 26", "first_release_date": 1758844800},
        {"id": 4, "name": "FC alternate release", "first_release_date": 1758931200},
        {"id": 5, "name": "FC unknown release"},
    ]
    request = Mock(side_effect=[{"access_token": "test", "expires_in": 3600}, games])
    monkeypatch.setattr(catalog, "_request_json", request)
    client = catalog.IGDBClient("fake", "fake")
    result = client.search_games("FC")
    assert [game["id"] for game in result] == [2, 4, 3, 1, 5]
    assert client.search_games("fc") == result
    assert request.call_count == 2


@pytest.mark.parametrize("date", [None, "2027", True, {}, 10**100])
def test_invalid_release_dates_sort_after_known_dates(date):
    unknown = {"id": 1, "name": "A", "first_release_date": date}
    known = {"id": 2, "name": "Z", "first_release_date": 946684800}
    assert sorted([unknown, known], key=catalog.release_date_sort_key) == [known, unknown]


def test_release_date_ties_are_deterministic():
    games = [{"id": 3, "name": "Z", "first_release_date": 946684800},
             {"id": 2, "name": "A", "first_release_date": 946684800},
             {"id": 1, "name": "A", "first_release_date": 946684800}]
    assert [g["id"] for g in sorted(games, key=catalog.release_date_sort_key)] == [1, 2, 3]


def test_search_prioritizes_exact_then_prefix_then_other_matches(monkeypatch):
    games = [
        {"id": 1, "name": "The Resident Evil 4 story", "first_release_date": 1800000000},
        {"id": 2, "name": "Resident Evil 4 Gold", "first_release_date": 1700000000},
        {"id": 3, "name": "Resident Evil 4", "first_release_date": 1100000000},
        {"id": 4, "name": "Resident Evil 4 Deluxe", "first_release_date": 1750000000},
        {"id": 5, "name": "Resident Evil 4"},
    ]
    request = Mock(side_effect=[{"access_token": "test", "expires_in": 3600}, games])
    monkeypatch.setattr(catalog, "_request_json", request)
    client = catalog.IGDBClient("fake", "fake")
    result = client.search_games("Resident Evil 4")
    assert [game["id"] for game in result] == [3, 5, 4, 2, 1]
    assert client.search_games("resident evil 4") == result
    assert request.call_count == 2


@pytest.mark.parametrize("term", ["resident evil 4", "RESIDENT EVIL 4", "  Resident   Evil 4  "])
def test_relevance_ignores_case_and_extra_spaces(term):
    exact = {"id": 1, "name": "Resident Evil 4"}
    prefix = {"id": 2, "name": "Resident Evil 4 Gold", "first_release_date": 1700000000}
    other = {"id": 3, "name": "The Resident Evil 4 story", "first_release_date": 1800000000}
    result = sorted([other, prefix, exact], key=lambda game: catalog.search_sort_key(game, term))
    assert result == [exact, prefix, other]


def test_get_game_uses_numeric_id_and_cache(monkeypatch):
    game = {"id": 123, "name": "Portal 2"}
    request = Mock(side_effect=[{"access_token": "test", "expires_in": 3600}, [game]])
    monkeypatch.setattr(catalog, "_request_json", request)
    client = catalog.IGDBClient("fake", "fake")
    assert client.get_game(123) == game
    assert client.get_game(123) == game
    assert request.call_count == 2
    assert "where id = 123;" in request.call_args.args[0].data.decode()


@pytest.mark.parametrize("game_id", [0, -1, True, "1; limit 99;", 2**63])
def test_invalid_lookup_id_never_reaches_network(game_id):
    assert catalog.IGDBClient("fake", "fake").get_game(game_id) is None


@pytest.mark.parametrize("game", [None, {"id": 1, "name": "Pack", "game_type": {"type": "Pack"}},
                                  {"id": 1, "name": "Edition", "version_parent": 2}])
def test_lookup_rejects_missing_or_noncanonical_game(monkeypatch, game):
    monkeypatch.setattr(catalog, "_request_json", Mock(side_effect=[
        {"access_token": "test", "expires_in": 3600}, [game] if game else [],
    ]))
    assert catalog.IGDBClient("fake", "fake").get_game(1) is None


@pytest.mark.parametrize("game_id", ["", "999", "abc", "1; drop table games", "9" * 100])
def test_create_requires_real_catalog_selection(post_form, game_data, stored_games, game_id):
    response = post_form("/games/new", {**game_data, "igdb_id": game_id})
    assert response.status_code == 200
    assert b"choose a game from the catalog" in response.data
    assert stored_games() == []


@pytest.mark.parametrize("changes", [{"platform": "Xbox 360"}, {"title": "Invented game"}])
def test_create_rejects_tampered_metadata(post_form, game_data, stored_games, changes):
    response = post_form("/games/new", {**game_data, **changes})
    assert response.status_code == 200
    assert stored_games() == []


def test_selected_game_survives_validation_error(post_form, game_data):
    page = post_form("/games/new", {**game_data, "rating": "11"}).get_data(as_text=True)
    assert 'value="123"' in page
    assert 'value="PC" selected' in page
    assert 'value="PS3"' in page


def test_add_form_initially_disables_platform(client):
    page = client.get("/games/new").get_data(as_text=True)
    assert "Choose a game first" in page
    assert 'aria-describedby="platform-message" disabled' in page


def test_details_endpoint_returns_platforms(client, app, game_data):
    response = client.get("/catalog/games/123")
    assert response.status_code == 200
    assert response.json["game"]["platforms"] == ["PC", "PS3"]
    assert client.get("/catalog/games/999").status_code == 404


def test_catalog_outage_does_not_save(post_form, game_data, app, stored_games):
    app.extensions["igdb_client"].get_game.side_effect = catalog.CatalogError("private-error")
    response = post_form("/games/new", game_data)
    assert b"catalog is unavailable" in response.data
    assert b"private-error" not in response.data
    assert stored_games() == []


def test_details_outage_returns_safe_json(client, app, game_data):
    app.extensions["igdb_client"].get_game.side_effect = catalog.CatalogError("private-error")
    response = client.get("/catalog/games/123")
    assert response.status_code == 503
    assert b"private-error" not in response.data


def test_game_without_platforms_cannot_be_added(post_form, game_data, app, stored_games):
    app.extensions["igdb_client"].get_game.side_effect = None
    app.extensions["igdb_client"].get_game.return_value = {"id": 123, "name": "Portal 2"}
    response = post_form("/games/new", game_data)
    assert b"choose an available platform" in response.data
    assert stored_games() == []


def test_new_game_keeps_catalog_identity_and_strict_edit(post_form, game_data, stored_games, client):
    assert post_form("/games/new", game_data).status_code == 302
    saved = stored_games()[0]
    assert saved["igdb_id"] == 123
    url = f"/games/{saved['id']}/edit"
    assert b'<select id="platform"' in client.get(url).data
    assert post_form(url, {**game_data, "platform": "Xbox 360"}).status_code == 200
    assert stored_games()[0] == saved
    assert post_form(url, {**game_data, "title": "Fake"}).status_code == 200
    assert stored_games()[0] == saved
    assert post_form(url, {**game_data, "platform": "PS3", "rating": ""}).status_code == 302
    assert stored_games()[0]["platform"] == "PS3"
    assert stored_games()[0]["rating"] is None


def test_additive_migration_preserves_legacy_entries(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, title TEXT)")
        connection.execute("INSERT INTO games (title) VALUES ('Existing game')")
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    with application.app_context():
        row = get_db().execute("SELECT * FROM games").fetchone()
        assert row["title"] == "Existing game"
        assert row["igdb_id"] is None
    with application.app_context():
        assert get_db().execute("SELECT count(*) FROM games").fetchone()[0] == 1
