from concurrent.futures import ThreadPoolExecutor

from app.db import get_db
from tests.conftest import CSRFTokenParser


def test_duplicate_creation_preserves_game_and_entered_values(post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    before = stored_games()
    response = post_form("/library/add", {**game_data, "rating": "7", "review": "Keep this draft"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "already in your collection for this platform" in page
    assert f'href="/library/entries/{before[0]["id"]}/edit"' in page
    assert 'value="123"' in page
    assert 'value="PC" selected' in page
    assert "Keep this draft" in page
    assert stored_games() == before


def test_same_game_on_different_platforms_is_allowed(post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    assert post_form("/library/add", {**game_data, "platform": "PS3"}).status_code == 302
    assert {game["platform"] for game in stored_games()} == {"PC", "PS3"}


def test_distinct_catalog_ids_with_identical_titles_are_allowed(app, post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    app.extensions["igdb_client"].get_game.side_effect = lambda game_id: {
        "id": game_id, "name": "Portal 2", "platforms": [{"name": "PC"}],
    }
    assert post_form("/library/add", {**game_data, "igdb_id": "456"}).status_code == 302
    assert {game["igdb_id"] for game in stored_games()} == {123, 456}


def test_edit_cannot_move_game_to_already_owned_platform(post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    assert post_form("/library/add", {**game_data, "platform": "PS3"}).status_code == 302
    before = stored_games()
    response = post_form(f"/library/entries/{before[1]['id']}/edit", game_data)
    assert response.status_code == 200
    assert b"already in your collection" in response.data
    assert stored_games() == before


def test_editing_own_rating_does_not_report_duplicate(post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    game_id = stored_games()[0]["id"]
    assert post_form(f"/library/entries/{game_id}/edit", {**game_data, "rating": ""}).status_code == 302
    assert len(stored_games()) == 1
    assert stored_games()[0]["rating"] is None


def test_preexisting_duplicates_remain_editable_and_are_not_deleted(
    app, seed_game, post_form, game_data, stored_games
):
    first = seed_game()
    seed_game()
    with app.app_context():
        get_db().execute("UPDATE games SET igdb_id = 123")
        get_db().commit()
    assert post_form(f"/library/entries/{first}/edit", {**game_data, "status": "Completed"}).status_code == 302
    assert len(stored_games()) == 2
    assert stored_games()[0]["status"] == "Completed"
    assert post_form("/library/add", game_data).status_code == 200
    assert len(stored_games()) == 2


def test_existing_catalog_platform_ignores_case_and_surrounding_spaces(
    app, seed_game, post_form, game_data, stored_games
):
    seed_game(platform=" pc ")
    with app.app_context():
        get_db().execute("UPDATE games SET igdb_id = 123")
        get_db().commit()
    before = stored_games()
    assert post_form("/library/add", game_data).status_code == 200
    assert stored_games() == before


def test_legacy_edit_cannot_create_another_manual_duplicate(
    seed_game, post_form, game_data, stored_games
):
    seed_game(title="Portal 2", platform="PC")
    other_id = seed_game(title="Other game", platform="PC")
    before = stored_games()
    response = post_form(f"/library/entries/{other_id}/edit", {**game_data, "title": "portal 2"})
    assert response.status_code == 200
    assert b"already in your collection" in response.data
    assert stored_games() == before


def test_legacy_name_alone_does_not_identify_a_catalog_game(seed_game, post_form, game_data, stored_games):
    seed_game()
    assert post_form("/library/add", game_data).status_code == 302
    assert len(stored_games()) == 2


def test_simultaneous_duplicate_submissions_only_save_once(app, game_data, stored_games):
    def submit():
        with app.test_client() as client:
            page = client.get("/library/add")
            parser = CSRFTokenParser()
            parser.feed(page.get_data(as_text=True))
            return client.post("/library/add", data={**game_data, "csrf_token": parser.token}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(statuses) == [200, 302]
    assert len(stored_games()) == 1
