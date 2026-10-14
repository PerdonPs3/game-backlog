import pytest


def test_empty_collection(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"No games yet" in response.data


def test_create_game_persists(app, post_form, game_data, stored_games):
    response = post_form("/games/new", game_data)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    game = stored_games()[0]
    assert game["title"] == "Portal 2"
    assert game["rating"] == 9
    assert game["review"] == game_data["review"]
    # A fresh client/request must see the saved game too.
    page = app.test_client().get("/")
    assert b"Portal 2" in page.data
    assert b"Rating: 9/10" in page.data


def test_create_without_rating_or_review(post_form, game_data, stored_games):
    data = {key: value for key, value in game_data.items()
            if key not in ("rating", "review")}
    assert post_form("/games/new", data).status_code == 302
    assert stored_games()[0]["rating"] is None
    assert stored_games()[0]["review"] == ""


INVALID_FIELDS = [
    ("title", "   ", "Title must contain"),
    ("title", "x" * 201, "Title must contain"),
    ("platform", "   ", "Platform must contain"),
    ("platform", "x" * 81, "Platform must contain"),
    ("status", "Unknown", "Please select a valid status"),
    ("rating", "0", "Rating must be a whole number"),
    ("rating", "11", "Rating must be a whole number"),
    ("rating", "8.5", "Rating must be a whole number"),
    ("rating", "abc", "Rating must be a whole number"),
    ("review", "x" * 2001, "Review must contain no more than"),
]


@pytest.mark.parametrize("field,value,message", INVALID_FIELDS)
def test_invalid_creation_does_not_save(
    post_form, game_data, stored_games, field, value, message
):
    response = post_form("/games/new", {**game_data, field: value})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert stored_games() == []


def test_edit_updates_only_selected_game(
    client, post_form, game_data, seed_game, stored_games
):
    game_id = seed_game()
    seed_game(title="Another game")
    other_before = stored_games()[1]
    page = client.get(f"/games/{game_id}/edit")
    assert b'value="9"' in page.data
    assert b"A great puzzle game." in page.data
    response = post_form(f"/games/{game_id}/edit", {
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
    response = post_form(f"/games/{game_id}/edit", {
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
    response = post_form(f"/games/{game_id}/edit", {**game_data, field: value})
    assert response.status_code == 200
    assert message in response.get_data(as_text=True)
    assert stored_games() == before


def test_filter_by_status(client, seed_game):
    seed_game(title="Finished game", status="Completed")
    seed_game(title="Pending game", status="Backlog")
    response = client.get("/?status=Completed")
    assert response.status_code == 200
    assert b"Finished game" in response.data
    assert b"Pending game" not in response.data
    assert b"Pending game" in client.get("/").data
    assert client.get("/?status=Unknown").status_code == 400


def test_delete_requires_confirmation_and_preserves_other_games(
    client, post_form, seed_game, stored_games
):
    game_id = seed_game()
    seed_game(title="Keep this game")
    before = stored_games()
    assert client.get(f"/games/{game_id}/delete").status_code == 200
    assert stored_games() == before
    assert client.get("/").status_code == 200
    assert stored_games() == before
    assert post_form(f"/games/{game_id}/delete", {}).status_code == 302
    assert stored_games() == [before[1]]


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_missing_game_returns_404(client, action):
    assert client.get(f"/games/999/{action}").status_code == 404


def test_posts_without_csrf_token_are_rejected(
    client, game_data, seed_game, stored_games
):
    game_id = seed_game()
    before = stored_games()
    for url in ("/games/new", f"/games/{game_id}/edit", f"/games/{game_id}/delete"):
        assert client.post(url, data=game_data).status_code == 400
    assert stored_games() == before


def test_review_is_escaped_in_html(client, post_form, game_data):
    review = "<script>alert('test')</script>"
    assert post_form("/games/new", {**game_data, "review": review}).status_code == 302
    page = client.get("/")
    assert b"<script>" not in page.data
    assert b"&lt;script&gt;" in page.data
