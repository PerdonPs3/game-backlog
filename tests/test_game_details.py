from unittest.mock import Mock

import pytest

from app.catalog import CatalogError, game_profile
from app.db import get_db


def link_catalog(app, game_id):
    with app.app_context():
        db = get_db()
        db.execute("UPDATE games SET igdb_id = 123, is_favorite = 1 WHERE id = ?", (game_id,))
        db.commit()


def test_legacy_details_without_catalog(client, seed_game, app, stored_games):
    game_id = seed_game(review="My memories", rating=None)
    catalog = Mock()
    app.extensions["igdb_client"] = catalog
    before = stored_games()
    page = client.get(f"/games/{game_id}")
    assert page.status_code == 200
    assert b"My memories" in page.data
    assert b"Not rated yet" in page.data
    assert b"not linked to the catalog" in page.data
    catalog.get_game.assert_not_called()
    assert stored_games() == before


def test_catalog_details_fragment_escaped(client, seed_game, app, stored_games):
    game_id = seed_game(review="<script>personal()</script>")
    link_catalog(app, game_id)
    app.extensions["igdb_client"].get_game.return_value = {
        "summary": "<script>catalog()</script>", "genres": [{"name": "Puzzle"}],
        "first_release_date": 1303171200,
    }
    app.extensions["igdb_client"].get_game.side_effect = None
    before = stored_games()
    page = client.get(f"/games/{game_id}", headers={"Accept": "application/json"})
    html = page.json["html"]
    assert "Puzzle" in html and "2011-04-19" in html
    assert "Favorite" in html and "4.5/5" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "<!DOCTYPE" not in html
    assert "Accept" in page.headers["Vary"]
    assert page.headers["Cache-Control"] == "no-store"
    assert stored_games() == before


@pytest.mark.parametrize("failure", [None, CatalogError("secret upstream response")])
def test_catalog_failure_keeps_notes(client, seed_game, app, failure):
    game_id = seed_game(review="Keep my notes")
    link_catalog(app, game_id)
    catalog = Mock()
    catalog.get_game.return_value = None
    if failure:
        catalog.get_game.side_effect = failure
    app.extensions["igdb_client"] = catalog
    page = client.get(f"/games/{game_id}")
    assert page.status_code == 200
    assert b"Keep my notes" in page.data
    assert b"secret upstream" not in page.data


def test_missing_details(client, app):
    catalog = Mock()
    app.extensions["igdb_client"] = catalog
    assert client.get("/games/999").status_code == 404
    catalog.get_game.assert_not_called()


def test_profile_invalid_optional_data():
    assert game_profile({"summary": {}, "genres": {}, "first_release_date": True}) == {
        "summary": None, "genres": [], "release": None,
    }
    assert game_profile({"first_release_date": 10**100})["release"] is None
    assert game_profile({"genres": [{"name": "Puzzle"}, {"name": "Puzzle"}, None]})["genres"] == ["Puzzle"]


def test_details_links_survive_live_filter(client, seed_game):
    game_id = seed_game()
    page = client.get("/library")
    assert b'id="game-details-dialog"' in page.data
    assert b"game-details.js" in page.data
    assert b'id="collection-view-switch"' in page.data
    assert b'data-collection-view="shelf"' in page.data
    assert b"collection-view.js" in page.data
    html = client.get("/library?q=Portal", headers={"Accept": "application/json"}).json["html"]
    assert f'href="/games/{game_id}"' in html
    assert html.count("data-game-details") == 2


@pytest.mark.parametrize("rating,filled", [(1, 1), (10, 10), (None, 0)])
def test_personal_verdict_design(client, seed_game, rating, filled):
    game_id = seed_game(rating=rating, review="A memory\n" + "x" * 1000)
    html = client.get(f"/games/{game_id}").get_data(as_text=True)
    assert "Your review" in html
    assert 'class="verdict-quote"' in html
    assert html.count('class="is-filled"') == filled
    assert f'href="/games/{game_id}/edit"' in html
    assert "A memory\n" in html
    if rating is not None:
        assert f'aria-label="Your rating: {rating / 2:g}/5"' in html
    else:
        assert "Not rated yet" in html
