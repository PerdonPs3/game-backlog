import pytest


@pytest.mark.parametrize("page", ["index", "create", "edit", "delete"])
def test_pages_include_decorative_logo_and_illumination(client, seed_game, page):
    game_id = seed_game()
    urls = {"index": "/library", "create": "/games/new",
            "edit": f"/games/{game_id}/edit", "delete": f"/games/{game_id}/delete"}
    response = client.get(urls[page])
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-easter-egg-logo aria-hidden="true"' in html
    assert 'src="/static/cursor-glow.js"' in html
    assert html.count('id="brand-gold"') == 1
    assert '<g id="brand-symbol"' in html
    assert 'M65 85 150 110 166 140' in html
    assert 'M85 146 164 191 218 327' not in html
    assert 'M365 54 272 126' not in html
