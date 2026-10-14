import pytest


@pytest.mark.parametrize("page", ["index", "create", "edit", "delete"])
def test_pages_include_decorative_logo_and_illumination(client, seed_game, page):
    game_id = seed_game()
    urls = {"index": "/", "create": "/games/new",
            "edit": f"/games/{game_id}/edit", "delete": f"/games/{game_id}/delete"}
    response = client.get(urls[page])
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-easter-egg-logo aria-hidden="true"' in html
    assert 'src="/static/cursor-glow.js"' in html
    assert html.count('id="brand-gold"') == 1
