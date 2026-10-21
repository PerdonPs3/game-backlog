"""Exercise profile display, ordering, and adversarial account isolation."""

import psycopg
import pytest

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


@pytest.fixture
def players(accounts):
    alice, bob = sign_in(accounts, "alice"), sign_in(accounts, "bob")
    with accounts.app_context():
        db = get_db()
        own = [db.execute("INSERT INTO games (title, platform, owner_id) VALUES (?, 'PC', ?) RETURNING id", (f"Alice pick {number}", ALICE)).fetchone()[0] for number in range(6)]
        foreign = db.execute("INSERT INTO games (title, platform, owner_id) VALUES ('Bob private title', 'PC', ?) RETURNING id", (BOB,)).fetchone()[0]
        legacy = db.execute("INSERT INTO games (title, platform) VALUES ('Unowned private title', 'PC') RETURNING id").fetchone()[0]
    return alice, bob, own, foreign, legacy


def stored(application, owner=ALICE):
    with application.app_context():
        return [(row["position"], row["game_id"]) for row in get_db().execute("SELECT position, game_id FROM profile_showcase WHERE owner_id = ? ORDER BY position", (owner,))]


def test_profile_overview_and_showcase_editor_have_distinct_private_routes(accounts, players):
    alice, bob, own, _, _ = players
    page = alice.get("/account/profile").get_data(as_text=True)
    assert "Showcase" in page and "Playing now" in page and "Recent completions" in page
    assert "Build your showcase" in page and 'name="display_name"' not in page
    assert '/account/profile/edit' in page
    editor = alice.get("/account/profile/showcase").get_data(as_text=True)
    assert editor.count('name="games"') == 5
    assert "Bob private title" not in editor and "Unowned private title" not in editor
    ids = [own[4], own[0], own[2]]
    result = submit(alice, "/account/profile/showcase", {"games": [str(value) for value in ids]})
    assert result.status_code == 303 and result.location.endswith("/account/profile#profile-feedback")
    page = alice.get(result.location).get_data(as_text=True)
    assert "Showcase saved" in page
    assert page.index('Alice pick 4') < page.index('Alice pick 0') < page.index('Alice pick 2')
    assert stored(accounts) == list(enumerate(ids, 1))
    assert 'Alice pick' not in bob.get("/account/profile").get_data(as_text=True)
    assert 'Showcase saved' not in alice.get("/account/profile").get_data(as_text=True)


def test_invalid_showcase_never_replaces_previous_games(accounts, players):
    alice, _, own, foreign, legacy = players
    assert submit(alice, "/account/profile/showcase", {"games": [str(own[0])]}).status_code == 303
    for values in ([str(value) for value in own], [str(own[0]), str(own[0])], [str(own[0]), '0' + str(own[0])], [str(foreign)], [str(legacy)], ['-1'], ['1; DROP TABLE games'], ['9' * 30], ['does-not-exist']):
        response = submit(alice, "/account/profile/showcase", {"games": values})
        assert response.status_code == 200 and 'role="alert"' in response.get_data(as_text=True)
        assert stored(accounts) == [(1, own[0])]
    assert alice.post("/account/profile/showcase", data={"games": str(own[1])}).status_code == 400


def test_reordering_clearing_and_game_deletion_keep_the_showcase_consistent(accounts, players):
    alice, _, own, _, _ = players
    submit(alice, "/account/profile/showcase", {"games": [str(own[1]), '', str(own[0]), '', '']})
    assert stored(accounts) == [(1, own[1]), (2, own[0])]
    submit(alice, "/account/profile/showcase", {"games": [str(own[0]), str(own[1])]})
    assert stored(accounts) == [(1, own[0]), (2, own[1])]
    with accounts.app_context():
        get_db().execute("DELETE FROM games WHERE id = ? AND owner_id = ?", (own[0], ALICE))
    assert stored(accounts) == [(2, own[1])]
    assert alice.get("/account/profile").status_code == 200
    submit(alice, "/account/profile/showcase", {"games": ['', '', '', '', '']})
    assert stored(accounts) == []


def test_database_rejects_cross_owner_entries_and_more_than_five_positions(accounts, players):
    _, _, own, foreign, _ = players
    with accounts.app_context():
        db = get_db()
        with pytest.raises(psycopg.IntegrityError):
            db.execute("INSERT INTO profile_showcase VALUES (?, 1, ?)", (ALICE, foreign))
        with pytest.raises(psycopg.IntegrityError):
            db.execute("INSERT INTO profile_showcase VALUES (?, 6, ?)", (ALICE, own[0]))


def test_activity_only_uses_current_accounts_entries_and_recorded_completion_dates(accounts, players):
    alice, bob, own, foreign, _ = players
    with accounts.app_context():
        db = get_db()
        db.execute("UPDATE games SET status = 'Playing' WHERE id = ?", (own[0],))
        db.execute("UPDATE games SET status = 'Completed', completed_on = '2026-09-10' WHERE id = ?", (own[1],))
        db.execute("UPDATE games SET status = 'Completed', completed_on = '2026-10-10' WHERE id = ?", (own[2],))
        db.execute("UPDATE games SET status = 'Completed' WHERE id = ?", (own[3],))
        db.execute("UPDATE games SET status = 'Playing' WHERE id = ?", (foreign,))
    page = alice.get("/account/profile").get_data(as_text=True)
    assert 'Alice pick 0' in page and '2026-10-10' in page and '2026-09-10' in page
    assert page.index('Alice pick 2') < page.index('Alice pick 1')
    assert 'Alice pick 3' not in page and 'Bob private title' not in page
    assert 'Alice pick' not in bob.get("/account/profile?user_id=" + ALICE).get_data(as_text=True)


def test_anonymous_setup_recovery_and_empty_library_behaviors(accounts):
    client = accounts.test_client()
    for path in ("/account/profile", "/account/profile/edit", "/account/profile/showcase"):
        assert client.get(path).location.endswith('/account/login')
    client = sign_in(accounts, 'alice', complete_profile=False)
    assert client.get('/account/profile').location.endswith('/account/profile/edit')
    assert client.get('/account/profile/showcase').location.endswith('/account/profile/edit')
    result = submit(client, '/account/profile/edit', {'display_name':'Alice', 'username':'alice_player'})
    assert result.location.endswith('/account/alice_player/profile#profile-feedback')
    page = client.get(result.location).get_data(as_text=True)
    assert 'Add your first game' in page and '<dd>0<small>%</small></dd>' in page
    assert 'Your showcase starts with a game' in client.get('/account/alice_player/profile/showcase').get_data(as_text=True)
    submit(client, '/account/logout', {}, source='/account/profile/edit')
    result = submit(client, '/account/verify-recovery', {'email':'alice@example.test','code':'123456'})
    assert result.location.endswith('/account/password')
    for path in ('/account/profile', '/account/profile/showcase', '/account/profile/edit'):
        assert client.get(path).location.endswith('/account/password')


def test_legacy_profile_post_still_saves_without_exposing_another_account(accounts, players):
    alice, bob, _, _, _ = players
    result = submit(alice, '/account/profile', {'display_name':'Updated Alice'}, source='/account/profile/edit')
    assert result.status_code == 303
    assert 'Updated Alice' in alice.get('/account/profile').get_data(as_text=True)
    assert 'Updated Alice' not in bob.get('/account/profile').get_data(as_text=True)
