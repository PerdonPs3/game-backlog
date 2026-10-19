import re

import pytest

from app.db import get_db


def titles(response):
    html = response.json["html"] if response.is_json else response.get_data(as_text=True)
    return [re.sub(r"<[^>]*>", "", title) for title in re.findall(r"<h2>(.*?)</h2>", html)]


def test_default_sort_keeps_recently_added_first(client, seed_game):
    seed_game(title="First game")
    seed_game(title="Second game")
    assert titles(client.get("/library")) == ["Second game", "First game"]


@pytest.mark.parametrize("sort, expected", [
    ("newest", ["Newer game", "Older game"]),
    ("oldest", ["Older game", "Newer game"]),
])
def test_date_sort_uses_added_date_not_just_id(app, client, seed_game, sort, expected):
    newest = seed_game(title="Newer game")
    oldest = seed_game(title="Older game")
    with app.app_context():
        db = get_db()
        db.execute("UPDATE games SET created_at = '2025-01-01' WHERE id = ?", (oldest,))
        db.execute("UPDATE games SET created_at = '2026-01-01' WHERE id = ?", (newest,))
        db.commit()
    assert titles(client.get("/library", query_string={"sort": sort})) == expected


def test_title_sort_ignores_ascii_case_and_has_stable_ties(client, seed_game):
    for title in ["Zelda", "portal", "Alien", "alien"]:
        seed_game(title=title)
    assert titles(client.get("/library?sort=title")) == ["Alien", "alien", "portal", "Zelda"]


def test_highest_rating_puts_unrated_last_and_handles_ties(client, seed_game):
    seed_game(title="Unrated first", rating=None)
    seed_game(title="Good", rating=7)
    seed_game(title="Great first", rating=10)
    seed_game(title="Great second", rating=10)
    seed_game(title="Unrated second", rating=None)
    assert titles(client.get("/library?sort=rating")) == [
        "Great second", "Great first", "Good", "Unrated second", "Unrated first",
    ]


def test_sort_combines_with_search_status_and_live_responses(client, seed_game, stored_games):
    seed_game(title="Resident B", status="Completed", rating=8)
    seed_game(title="Resident A", status="Completed", rating=10)
    seed_game(title="Resident C", status="Playing", rating=9)
    seed_game(title="Portal", status="Completed", rating=10)
    before = stored_games()
    url = "/library?q=res&status=Completed&sort=title"
    assert titles(client.get(url)) == ["Resident A", "Resident B"]
    live = client.get(url, headers={"Accept": "application/json"})
    assert titles(live) == ["Resident A", "Resident B"]
    assert live.json["count"] == 2
    assert stored_games() == before


def test_selected_sort_survives_reload_and_clear_filter_link(client, seed_game):
    seed_game()
    page = client.get("/library?q=portal&sort=rating").get_data(as_text=True)
    assert '<option value="rating" selected>' in page
    assert 'href="/library?sort=rating">Clear filters</a>' in page


@pytest.mark.parametrize("sort", ["", "unknown", "rating DESC; DROP TABLE games;--"])
def test_invalid_sort_never_reaches_sql(client, seed_game, stored_games, sort):
    seed_game()
    before = stored_games()
    assert client.get("/library", query_string={"sort": sort}).status_code == 400
    assert client.get("/library", query_string={"sort": sort}, headers={"Accept": "application/json"}).status_code == 400
    assert stored_games() == before


def test_sorting_does_not_change_global_statistics(client, seed_game):
    seed_game()
    seed_game(status="Completed")
    original = re.search(r'<section id="collection-summary".*?</section>', client.get("/library").get_data(as_text=True), re.S).group(0)
    sorted_summary = re.search(r'<section id="collection-summary".*?</section>', client.get("/library?sort=rating").get_data(as_text=True), re.S).group(0)
    assert sorted_summary == original
