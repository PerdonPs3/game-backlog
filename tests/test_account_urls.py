"""Account slugs describe an address; session identity still controls all data."""

import pytest

from app.db import get_db
from app.public_profiles import claim_username
from tests.test_accounts import ALICE, BOB, accounts, libraries, sign_in, submit


@pytest.fixture
def named_libraries(accounts, libraries):
    with accounts.app_context():
        for owner, username in ((ALICE, "alice_player"), (BOB, "bob_player")):
            claim_username(get_db(), owner, username)
            get_db().execute("UPDATE profiles SET username = ? WHERE id = ?", (username, owner))
    return libraries


@pytest.mark.parametrize("suffix,legacy", [
    ("library", "/account/{username}/library"), ("profile", "/account/profile"),
    ("profile/edit", "/account/profile/edit"),
    ("profile/showcase", "/account/profile/showcase"),
    ("profile/sharing", "/account/profile/sharing"),
])
def test_legacy_links_redirect_to_the_owners_account(named_libraries, suffix, legacy):
    alice, bob, _ = named_libraries
    for client, name in ((alice, "alice_player"), (bob, "bob_player")):
        result = client.get(legacy.format(username=name))
        assert result.status_code == 302
        expected = f"/players/{name}" if suffix == "profile" else '/settings/profile#profile-privacy' if suffix == 'profile/sharing' else {'library':'/library','profile/edit':'/settings/profile','profile/showcase':'/settings/profile/showcase'}[suffix]
        assert result.location == expected
        assert result.headers["Cache-Control"] == "private, no-store"
        page = client.get(result.location)
        assert page.status_code == 200
        assert f'/players/{name}' in page.text
        assert 'href="/library"' in page.text
        assert 'href="/account/profile"' not in page.text


@pytest.mark.parametrize("suffix", ["library", "profile", "profile/edit", "profile/showcase", "profile/sharing"])
def test_slugs_never_grant_another_accounts_access(named_libraries, suffix):
    alice, bob, _ = named_libraries
    for client, other in ((alice, "bob_player"), (bob, "alice_player")):
        for slug in (other, "unknown_player"):
            response = client.get(f"/account/{slug}/{suffix}")
            assert response.status_code == 404
            assert "secret game" not in response.text
            assert response.headers["Cache-Control"] == "private, no-store"


def test_library_filters_and_json_keep_the_same_ownership(named_libraries):
    alice, _, _ = named_libraries
    query = "q=alice&status=Backlog&sort=title&_external=https%3A%2F%2Fevil.example&username=bob_player"
    old = alice.get("/account/alice_player/library?" + query)
    assert old.location == "/library?" + query
    page = alice.get(old.location)
    assert page.status_code == 200 and "alice secret game" in page.text
    assert "bob secret game" not in page.text
    for path in ("/library", "/account/alice_player/library"):
        response = alice.get(path, headers={"Accept": "application/json"})
        assert response.status_code == 200
        assert response.json["count"] == 1
        assert "bob secret game" not in response.json["html"]
    assert alice.get("/account/bob_player/library", headers={"Accept": "application/json"}).status_code == 404


def test_old_names_redirect_only_for_the_owner_and_posts_remain_safe(accounts, named_libraries):
    alice, bob, _ = named_libraries
    with accounts.app_context():
        claim_username(get_db(), ALICE, "alice_renamed")
        get_db().execute("UPDATE profiles SET username = 'alice_renamed' WHERE id = ?", (ALICE,))
    for slug in ("alice_player", "ALICE_RENAMED"):
        response = alice.get(f"/account/{slug}/profile")
        assert response.location == "/players/alice_renamed"
        assert bob.get(f"/account/{slug}/profile").status_code == 404
    result = submit(alice, "/account/alice_player/profile/edit", {"display_name": "Renamed Alice"})
    assert result.status_code == 303
    assert result.location == "/settings/profile#profile-feedback"
    attack = submit(alice, "/account/bob_player/profile/edit", {"display_name": "Compromised"},
                    source="/account/alice_renamed/profile/edit")
    assert attack.status_code == 404
    with accounts.app_context():
        assert get_db().execute("SELECT display_name FROM profiles WHERE id = ?", (BOB,)).fetchone()[0] == "Bob"
    assert alice.post("/account/alice_renamed/profile/edit", data={"display_name": "No CSRF"}).status_code == 400


def test_setup_login_and_sharing_changes_use_the_current_identity(accounts):
    alice = sign_in(accounts, "alice", complete_profile=False)
    result = submit(alice, "/account/profile/edit", {"display_name": "Alice", "username": "alice_player"})
    assert result.location == "/players/alice_player#profile-feedback"
    assert alice.get(result.location).status_code == 200
    assert alice.get('/account/alice_player/profile/sharing').location == '/settings/profile#profile-privacy'
    with accounts.app_context():
        get_db().execute("UPDATE profiles SET username_changed_at = NULL WHERE id = ?", (ALICE,))
    result = submit(alice, '/account/alice_player/profile/sharing', {"username": "alice_renamed", "is_public": "yes"})
    assert result.location == "/settings/profile#profile-privacy"
    visitor = accounts.test_client()
    login = submit(visitor, "/account/login", {"email": "alice@example.test", "password": "test-password"})
    assert login.location == "/library"
    assert visitor.get('/players/alice_renamed').status_code == 200


def test_anonymous_recovery_and_offline_routes_do_not_expose_named_accounts(accounts, named_libraries, client):
    anonymous = accounts.test_client()
    for suffix in ("library", "profile", "profile/edit", "profile/showcase", "profile/sharing"):
        assert anonymous.get(f"/account/alice_player/{suffix}").location == "/account/login"
        assert client.get(f"/account/alice_player/{suffix}").status_code == 404
    assert anonymous.get('/account/alice_player/library', headers={"Accept": "application/json"}).status_code == 401
    alice, _, _ = named_libraries
    with accounts.app_context():
        get_db().execute("UPDATE account_sessions SET recovery = 1 WHERE user_id = ?", (ALICE,))
    assert alice.get('/account/alice_player/profile').location == '/account/password'


def test_switching_accounts_uses_the_new_identity_not_the_previous_session(accounts, named_libraries):
    alice, _, _ = named_libraries
    login = submit(alice, '/account/login', {"email": "bob@example.test", "password": "test-password"})
    assert login.location == '/library'
    assert alice.get(login.location).status_code == 200
    assert alice.get('/account/alice_player/profile').status_code == 404
    with accounts.app_context():
        get_db().execute("UPDATE profiles SET display_name = '', username = NULL, is_public = FALSE WHERE id = ?", (ALICE,))
    login = submit(alice, '/account/login', {"email": "alice@example.test", "password": "test-password"})
    assert login.location == '/settings/profile'
    assert alice.get(login.location).status_code == 200
