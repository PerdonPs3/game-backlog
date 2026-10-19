import pytest


@pytest.mark.parametrize("path", ["/", "/library", "/games/new", "/games/pick", "/backups/import", "/lists"])
def test_theme_available_on_all_page_shells(client, path):
    page = client.get(path)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert html.index("theme.js") < html.index("style.css") < html.index("light-theme.css")
    assert html.count("data-theme-toggle") == 1
    assert html.count('class="github-profile"') == 1
    assert 'href="https://github.com/PerdonPs3"' in html
    assert 'class="github-profile-name"' in html
    assert html.index("data-theme-toggle") < html.index('class="github-profile"')
    assert 'aria-label="Switch to light mode"' in html
    assert "data-theme-label" not in html
    assert 'class="theme-sun"' in html and 'class="theme-moon"' in html


def test_theme_available_in_edit_delete_and_details(client, seed_game):
    game_id = seed_game()
    for path in [f"/games/{game_id}", f"/games/{game_id}/edit", f"/games/{game_id}/delete"]:
        assert b"data-theme-toggle" in client.get(path).data
