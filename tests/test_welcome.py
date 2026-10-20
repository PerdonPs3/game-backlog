import pytest

from tests.test_accounts import accounts, sign_in


def test_welcome_is_private_by_default_and_does_not_access_collection(client, monkeypatch):
    def forbidden():
        raise AssertionError("Welcome page must not read personal collection or catalog")
    monkeypatch.setattr("app.routes.get_db", forbidden)
    monkeypatch.setattr("app.routes.get_catalog", forbidden)
    page = client.get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "VESTIGIUM" in html and "Every game" in html
    assert 'href="/explore"' in html
    assert 'href="https://github.com/PerdonPs3"' in html
    assert 'class="welcome-primary"' not in html
    assert 'class="welcome-backdrop" aria-hidden="true"' in html
    assert "t_cover_big/co4jni.jpg" in html
    assert 'action="/explore"' in html and 'data-catalog-url="/explore/suggestions"' in html
    assert 'href="#your-library"' in html and 'id="how-it-works"' in html
    assert 'class="welcome-header"' in html
    for image in ('home-library.png', 'home-profile.png'):
        assert image in html
        assert client.get('/static/images/' + image).status_code == 200
    assert "id=\"game-collection\"" not in html
    assert "Sign up" not in html
    assert "theme.js" in html and "light-theme.css" in html
    assert "welcome.js" in html and "favicon.svg" in html
    assert html.count('id="brand-symbol"') == 1


def test_library_remains_available_and_games_unchanged(client, seed_game, stored_games):
    seed_game(title="Private personal entry")
    before = stored_games()
    assert b"Private personal entry" not in client.get("/").data
    page = client.get("/library")
    assert b"Private personal entry" in page.data
    assert b"Vestigium" in page.data and b"Game Backlog" not in page.data
    assert stored_games() == before


def test_old_filter_links_redirect_safely(client, seed_game):
    seed_game(title="Portal 2")
    page = client.get("/?q=Portal&sort=rating")
    assert page.status_code == 302
    assert page.headers["Location"] == "/library?q=Portal&sort=rating"
    assert client.get("/", headers={"Accept": "application/json"}, follow_redirects=True).json["count"] == 1


@pytest.mark.parametrize("path", ["/games/new", "/backups/import", "/lists", "/games/pick"])
def test_workspace_has_vestigium_brand_and_home_link(client, path):
    html = client.get(path).get_data(as_text=True)
    assert 'class="workspace-brand" href="/"' in html
    assert "Vestigium" in html
    assert 'href="/library"' in html
    assert "View on GitHub" in html


def test_homepage_actions_distinguish_visitors_from_signed_in_members(accounts):
    guest = accounts.test_client().get('/').get_data(as_text=True)
    assert 'href="/account/login"' in guest and 'href="/account/register"' in guest
    assert 'Start your collection' in guest
    assert guest.count('>Create account</a>') == 1
    assert 'class="welcome-primary"' not in guest
    assert 'Back to your library' not in guest and 'Open your library' not in guest
    member = sign_in(accounts, 'alice').get('/').get_data(as_text=True)
    assert 'My profile' in member and 'Sign out' in member
    assert 'Open your library' in member
    assert 'alice@example.test' not in member
