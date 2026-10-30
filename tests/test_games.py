import pytest


def test_empty_collection(client):
    response = client.get("/library")
    assert response.status_code == 200
    assert b"No games yet" in response.data


def test_create_game_persists(app, post_form, game_data, stored_games):
    response = post_form("/library/add", game_data)
    assert response.status_code == 302
    assert response.headers["Location"] == "/games/123/portal-2#your-progress"
    game = stored_games()[0]
    assert game["title"] == "Portal 2"
    assert game["rating"] == 9
    assert game["review"] == game_data["review"]
    # A fresh client/request must see the saved game too.
    page = app.test_client().get("/library")
    assert b"Portal 2" in page.data
    assert b"Rating: 4.5/5" in page.data


def test_create_without_rating_or_review(post_form, game_data, stored_games):
    data = {key: value for key, value in game_data.items()
            if key not in ("rating", "review")}
    assert post_form("/library/add", data).status_code == 302
    assert stored_games()[0]["rating"] is None
    assert stored_games()[0]["review"] == ""


INVALID_FIELDS = [
    ("title", "   ", "Title must contain"),
    ("title", "x" * 201, "Title must contain"),
    ("platform", "   ", "Platform must contain"),
    ("platform", "x" * 81, "Platform must contain"),
    ("status", "Unknown", "Please select a valid status"),
    ("rating", "0", "Choose a rating from the five-star scale"),
    ("rating", "11", "Choose a rating from the five-star scale"),
    ("rating", "8.5", "Choose a rating from the five-star scale"),
    ("rating", "abc", "Choose a rating from the five-star scale"),
    ("review", "x" * 2001, "Review must contain no more than"),
]


@pytest.mark.parametrize("field,value,message", INVALID_FIELDS)
def test_invalid_creation_does_not_save(
    post_form, game_data, stored_games, field, value, message
):
    response = post_form("/library/add", {**game_data, field: value})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert stored_games() == []


def test_edit_updates_only_selected_game(
    client, post_form, game_data, seed_game, stored_games
):
    game_id = seed_game()
    seed_game(title="Another game")
    other_before = stored_games()[1]
    page = client.get(f"/library/entries/{game_id}/edit")
    assert b'value="9"' in page.data
    assert b"A great puzzle game." in page.data
    response = post_form(f"/library/entries/{game_id}/edit", {
        **game_data, "title": "Updated title", "platform": "PS3",
        "status": "Completed", "rating": "7", "review": "Updated review",
    })
    assert response.status_code == 302
    games = stored_games()
    assert games[0]["title"] == "Updated title"
    assert games[0]["platform"] == "PS3"
    assert games[0]["status"] == "Completed"
    assert games[0]["rating"] == 7
    assert games[0]["review"] == "Updated review"
    assert games[1] == other_before


@pytest.mark.parametrize("rating,review", [("", ""), ("   ", "   ")])
def test_edit_can_clear_rating_and_review(
    post_form, game_data, seed_game, stored_games, rating, review
):
    game_id = seed_game()
    response = post_form(f"/library/entries/{game_id}/edit", {
        **game_data, "rating": rating, "review": review,
    })
    assert response.status_code == 302
    assert stored_games()[0]["rating"] is None
    assert stored_games()[0]["review"] == ""


@pytest.mark.parametrize("field,value,message", INVALID_FIELDS)
def test_invalid_edit_preserves_saved_game(
    post_form, game_data, seed_game, stored_games, field, value, message
):
    game_id = seed_game()
    before = stored_games()
    response = post_form(f"/library/entries/{game_id}/edit", {**game_data, field: value})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert stored_games() == before


def test_filter_by_status(client, seed_game):
    seed_game(title="Finished game", status="Completed")
    seed_game(title="Pending game", status="Backlog")
    response = client.get("/library?status=Completed")
    assert response.status_code == 200
    assert b"Finished game" in response.data
    assert b"Pending game" not in response.data
    assert b"Pending game" in client.get("/library").data
    assert client.get("/library?status=Unknown").status_code == 400


def test_delete_requires_confirmation_and_preserves_other_games(
    client, post_form, seed_game, stored_games
):
    game_id = seed_game()
    seed_game(title="Keep this game")
    before = stored_games()
    assert client.get(f"/library/entries/{game_id}/delete").status_code == 200
    assert stored_games() == before
    assert client.get("/library").status_code == 200
    assert stored_games() == before
    assert post_form(f"/library/entries/{game_id}/delete", {}).status_code == 302
    assert stored_games() == [before[1]]


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_missing_game_returns_404(client, action):
    assert client.get(f"/library/entries/999/{action}").status_code == 404


def test_posts_without_csrf_token_are_rejected(
    client, game_data, seed_game, stored_games
):
    game_id = seed_game()
    before = stored_games()
    for url in ("/library/add", f"/library/entries/{game_id}/edit", f"/library/entries/{game_id}/delete"):
        assert client.post(url, data=game_data).status_code == 400
    assert stored_games() == before


def test_review_is_escaped_in_html(client, post_form, game_data):
    review = "<script>alert('test')</script>"
    assert post_form("/library/add", {**game_data, "review": review}).status_code == 302
    page = client.get("/library")
    assert b"<script>" not in page.data
    assert b"&lt;script&gt;" in page.data


@pytest.mark.parametrize("query", ["Resident", "resident", "RESIDENT", "  evil  "])
def test_search_matches_partial_title_ignoring_ascii_case(client, seed_game, query):
    seed_game(title="Resident Evil 4 Remake")
    seed_game(title="Resident Evil 2")
    seed_game(title="Portal 2")
    response = client.get("/library", query_string={"q": query})
    assert response.status_code == 200
    assert b"Resident Evil 4 Remake" in response.data
    assert b"Resident Evil 2" in response.data
    assert b"Portal 2" not in response.data


def test_search_and_status_filter_work_together(client, seed_game, stored_games):
    seed_game(title="Resident Finished", status="Completed")
    seed_game(title="Resident Pending", status="Backlog")
    seed_game(title="Portal Finished", status="Completed")
    before = stored_games()
    response = client.get("/library", query_string={"q": "Resident", "status": "Completed"})
    assert response.status_code == 200
    assert b"Resident Finished" in response.data
    assert b"Resident Pending" not in response.data
    assert b"Portal Finished" not in response.data
    assert b'value="Resident"' in response.data
    assert b"Clear filters" in response.data
    assert stored_games() == before


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_search_shows_all_games(client, seed_game, query):
    seed_game(title="Portal 2")
    seed_game(title="Hollow Knight")
    response = client.get("/library", query_string={"q": query})
    assert b"Portal 2" in response.data
    assert b"Hollow Knight" in response.data
    assert b"Clear filters" not in response.data


def test_no_search_matches_displays_helpful_message(client, seed_game):
    seed_game(title="Portal 2")
    response = client.get("/library", query_string={"q": "Resident"})
    assert response.status_code == 200
    assert b"No games match your search" in response.data
    assert b"No games yet" not in response.data
    assert b"Portal 2" not in response.data


@pytest.mark.parametrize("query", ["%", "_", "' OR 1=1 --"])
def test_search_treats_special_characters_as_literal_text(client, seed_game, query):
    seed_game(title="Portal 2")
    seed_game(title=f"Game containing {query}")
    response = client.get("/library", query_string={"q": query})
    assert response.status_code == 200
    assert b"Game containing" in response.data
    assert b"Portal 2" not in response.data


def test_search_input_is_escaped(client):
    response = client.get("/library", query_string={"q": '<script>alert("test")</script>'})
    assert response.status_code == 200
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_overlong_search_returns_400(client):
    assert client.get("/library", query_string={"q": "x" * 201}).status_code == 400
