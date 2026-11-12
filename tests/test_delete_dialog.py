from tests.conftest import CSRFTokenParser


def test_collection_contains_modal_and_delete_links(client, seed_game, stored_games):
    game_id = seed_game(title='Game "with quotes"')
    before = stored_games()
    page = client.get("/library").get_data(as_text=True)
    assert '<dialog id="delete-game-dialog"' in page
    assert 'aria-labelledby="delete-dialog-title"' in page
    assert 'data-delete-game data-game-title="Game &#34;with quotes&#34;"' in page
    assert f'href="/library/entries/{game_id}/delete?from=' in page
    assert "delete-confirmation.js" in page
    assert stored_games() == before


def test_modal_token_can_confirm_only_the_selected_game(client, seed_game, stored_games):
    target = seed_game()
    keep = seed_game(title="Keep this game")
    parser = CSRFTokenParser()
    parser.feed(client.get("/library").get_data(as_text=True))
    assert parser.token
    response = client.post(f"/library/entries/{target}/delete", data={"csrf_token": parser.token})
    assert response.status_code == 302
    assert [game["id"] for game in stored_games()] == [keep]


def test_live_filtered_cards_keep_modal_hooks(client, seed_game):
    seed_game(title="Resident Evil")
    fragment = client.get("/library?q=res", headers={"Accept": "application/json"}).json["html"]
    assert 'data-delete-game data-game-title="Resident Evil"' in fragment
