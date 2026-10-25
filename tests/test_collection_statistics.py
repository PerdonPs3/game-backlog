from app.db import get_db
from app.routes import collection_statistics


def stats_for(app):
    with app.app_context():
        return collection_statistics(get_db())


def test_empty_collection_has_safe_statistics(client, app):
    assert stats_for(app) == {
        "total": 0, "completed": 0, "playing": 0, "backlog": 0, "on_hold": 0, "dropped": 0,
        "rated": 0, "average": None, "completion_percent": 0,
    }
    page = client.get("/library").get_data(as_text=True)
    assert 'id="collection-summary"' not in page
    assert 'id="collection-filters"' in page


def test_statistics_count_statuses_and_ignore_unrated_games(app, client, seed_game):
    seed_game(status="Completed", rating=10)
    seed_game(status="Completed", rating=8)
    seed_game(status="Playing", rating=6)
    seed_game(status="Backlog", rating=None)
    assert stats_for(app) == {
        "total": 4, "completed": 2, "playing": 1, "backlog": 1, "on_hold": 0, "dropped": 0,
        "rated": 3, "average": 8.0, "completion_percent": 50,
    }


def test_filters_never_change_global_statistics(app, client, seed_game, stored_games):
    seed_game(title="Resident Evil", status="Completed")
    seed_game(title="Portal 2", status="Playing")
    before = stored_games()
    initial_stats = stats_for(app)
    assert client.get("/library?q=res&status=Completed").status_code == 200
    assert client.get("/library?q=no-match").status_code == 200
    assert stats_for(app) == initial_stats
    filtered = client.get("/library?q=res", headers={"Accept": "application/json"})
    assert filtered.json["count"] == 1
    assert "collection-summary" not in filtered.json["html"]
    assert stored_games() == before


def test_all_unrated_games_show_no_average(app, client, seed_game):
    seed_game(rating=None)
    seed_game(rating=None)
    assert stats_for(app)["rated"] == 0
    assert stats_for(app)["average"] is None


def test_all_completed_and_single_rating_have_correct_statistics(app, client, seed_game):
    seed_game(status="Completed", rating=9)
    assert stats_for(app)["completion_percent"] == 100
    assert stats_for(app)["rated"] == 1
    assert stats_for(app)["average"] == 9


def test_percentage_rounds_to_nearest_whole_number(app, seed_game):
    seed_game(status="Completed")
    for _ in range(7):
        seed_game(status="Backlog")
    assert stats_for(app)["completion_percent"] == 13


def test_platform_entries_count_separately(app, seed_game):
    seed_game(title="Portal 2", platform="PC", status="Completed")
    seed_game(title="Portal 2", platform="PS3", status="Backlog")
    stats = stats_for(app)
    assert stats["total"] == 2
    assert stats["completion_percent"] == 50


def test_statistics_reflect_edit_and_delete(app, seed_game, post_form, game_data):
    game_id = seed_game(status="Backlog", rating=9)
    assert stats_for(app)["completed"] == 0
    response = post_form(f"/games/{game_id}/edit", {**game_data, "status": "Completed", "rating": ""})
    assert response.status_code == 302
    stats = stats_for(app)
    assert stats["completed"] == 1
    assert stats["completion_percent"] == 100
    assert stats["rated"] == 0
    assert stats["average"] is None
    assert post_form(f"/games/{game_id}/delete", {}).status_code == 302
    assert stats_for(app)["total"] == 0


def test_statistics_reflect_new_catalog_game(app, post_form, game_data):
    assert post_form("/games/new", game_data).status_code == 302
    stats = stats_for(app)
    assert stats["total"] == 1
    assert stats["playing"] == 1
    assert stats["average"] == 9.0
