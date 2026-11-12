"""Existing scores retain their precision across every five-star presentation."""

import pytest


@pytest.mark.parametrize("units", range(1, 11))
def test_saved_rating_uses_five_stars_in_forms_cards_and_details(
    client, seed_game, stored_games, units
):
    game_id = seed_game(rating=units)
    before = stored_games()
    stars = format(units / 2, "g")
    editor = client.get(f"/library/entries/{game_id}/edit").get_data(as_text=True)
    assert f'aria-label="{stars} out of 5 stars" checked' in editor
    assert f'title="{stars}/5 stars"' in editor
    assert f'<output data-rating-score>{stars}/5</output>' in editor
    library = client.get("/library").get_data(as_text=True)
    assert f"Rating: {stars}/5" in library
    assert 'id="collection-summary"' not in library
    details = client.get(f"/library/entries/{game_id}", headers={"Accept": "application/json"}).json["html"]
    assert f'aria-label="Your rating: {stars}/5"' in details
    for page in (editor, library, details):
        assert "/10" not in page and "out of 10" not in page
    assert stored_games() == before
