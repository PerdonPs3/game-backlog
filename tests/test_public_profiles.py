"""Verify opt-in publication, minimal projections, and stable owner-only identities."""

import pytest
import psycopg

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


PATH = '/account/profile/sharing'


def test_private_by_default_and_selective_publication(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    with accounts.app_context():
        db = get_db()
        db.execute("UPDATE profiles SET bio = 'Alice public bio', avatar_image = ? WHERE id = ?", (b'private-photo', ALICE))
        own = db.execute("INSERT INTO games (title, platform, review, rating, status, owner_id) VALUES ('Chosen game', 'PC', 'SECRET REVIEW', 7, 'Playing', ?) RETURNING id", (ALICE,)).fetchone()[0]
        db.execute("INSERT INTO games (title, platform, owner_id) VALUES ('SECRET UNSELECTED', 'PC', ?)", (ALICE,))
        foreign = db.execute("INSERT INTO games (title, platform, owner_id) VALUES ('BOB SECRET', 'PC', ?) RETURNING id", (BOB,)).fetchone()[0]
        db.execute('INSERT INTO profile_showcase VALUES (?, 1, ?)', (ALICE, own))
        db.execute('INSERT INTO profile_showcase VALUES (?, 1, ?)', (BOB, foreign))
    anon = accounts.test_client()
    assert anon.get('/players/alice_player').status_code == 404
    result = submit(alice, PATH, {'username': 'Alice_Player'})
    assert result.status_code == 303
    assert 'profile is private' in alice.get(result.location).get_data(as_text=True)
    assert anon.get('/players/alice_player').status_code == 404
    submit(alice, PATH, {'username': 'alice_player', 'is_public': 'yes'})
    response = anon.get('/players/alice_player')
    page = response.get_data(as_text=True)
    assert response.status_code == 200 and '@alice_player' in page and 'Alice' in page
    assert 'Alice public bio' not in page and 'Chosen game' not in page
    submit(alice, PATH, {'username': 'alice_player', 'is_public': 'yes', 'share_bio': 'yes', 'share_showcase': 'yes'})
    response = anon.get('/players/alice_player')
    page = response.get_data(as_text=True)
    assert 'Chosen game' in page and 'Alice public bio' in page
    for private in ('SECRET REVIEW', 'SECRET UNSELECTED', 'BOB SECRET', '/games/', '/account/profile/photo', 'private-photo', '7/10', 'Playing', ALICE, BOB, 'alice@example.test', 'alice-access', 'alice-refresh'):
        assert private not in page
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    assert bob.get('/players/alice_player').status_code == 200
    assert 'BOB SECRET' not in bob.get('/players/alice_player').get_data(as_text=True)
    # Unsharing content and revoking the page take effect on the next request.
    submit(alice, PATH, {'username': 'alice_player', 'is_public': 'yes', 'share_bio': 'yes'})
    assert 'Chosen game' not in anon.get('/players/alice_player').get_data(as_text=True)
    submit(alice, PATH, {'username': 'alice_player'})
    assert anon.get('/players/alice_player').status_code == 404
    assert bob.get('/players/alice_player').status_code == 404
    assert alice.get('/players/alice_player').status_code == 404


def test_username_validation_uniqueness_and_owner_binding(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    for invalid in ('', 'ab', 'a' * 25, '123player', 'with space', 'bad/name', '<script>', 'pláyer', 'admin', 'VeStIgIuM', 'support'):
        response = submit(alice, PATH, {'username': invalid, 'is_public': 'yes'})
        assert response.status_code == 200 and 'role="alert"' in response.get_data(as_text=True)
    assert submit(alice, PATH, {'username': 'one_player'}).status_code == 303
    assert 'already taken' in submit(bob, PATH, {'username': 'ONE_PLAYER'}).get_data(as_text=True)
    assert 'permanent' in submit(alice, PATH, {'username': 'another_player'}).get_data(as_text=True)
    submit(bob, PATH, {'username': 'bob_player', 'is_public': 'yes', 'user_id': ALICE})
    with accounts.app_context():
        db = get_db()
        row = db.execute('SELECT username, is_public FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert row['username'] == 'one_player' and not row['is_public']
        assert db.execute('SELECT username FROM profiles WHERE id = ?', (BOB,)).fetchone()[0] == 'bob_player'
        with pytest.raises(psycopg.IntegrityError):
            db.execute("UPDATE profiles SET username = 'UPPERCASE' WHERE id = ?", (ALICE,))
        with pytest.raises(psycopg.IntegrityError):
            db.execute("UPDATE profiles SET username = NULL, is_public = TRUE WHERE id = ?", (ALICE,))
    assert alice.post(PATH, data={'username': 'one_player'}).status_code == 400
    assert accounts.test_client().post('/players/bob_player').status_code in (400, 405)
    assert accounts.test_client().get('/players/BOB_PLAYER').status_code == 404


def test_sharing_requires_normal_completed_session_and_public_output_escapes_text(accounts):
    anon = accounts.test_client()
    assert anon.get(PATH).location.endswith('/account/login')
    alice = sign_in(accounts, 'alice', complete_profile=False)
    assert alice.get(PATH).location.endswith('/account/profile/edit')
    submit(alice, '/account/profile/edit', {'display_name': '<script>alert(1)</script>', 'username':'safe_player', 'bio': '<img src=x onerror=alert(1)>'})
    submit(alice, PATH, {'username': 'safe_player', 'is_public': 'yes', 'share_bio': 'yes'})
    page = anon.get('/players/safe_player').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in page and '<img src=x' not in page
    assert '&lt;script&gt;' in page and '&lt;img' in page
    submit(alice, '/account/logout', {}, source=PATH)
    submit(alice, '/account/verify-recovery', {'email': 'alice@example.test', 'code': '123456'})
    assert alice.get(PATH).location.endswith('/account/password')
    assert alice.get('/players/safe_player').status_code == 200


def test_public_routes_are_unavailable_in_offline_mode(client):
    assert client.get('/players/offline_player').status_code == 404
    assert client.get(PATH).status_code == 404


def test_setup_publishes_by_default_and_accepts_capitals_without_publishing_extra_fields(accounts):
    alice = sign_in(accounts, 'alice', complete_profile=False)
    response = submit(alice, '/account/profile/edit', {'display_name':'Alice', 'username':'PerdonPs3', 'bio':'Private until selected'})
    assert response.status_code == 303
    anon = accounts.test_client()
    page = anon.get('/players/perdonps3')
    assert page.status_code == 200 and '@perdonps3' in page.get_data(as_text=True)
    assert 'Private until selected' not in page.get_data(as_text=True)
    # Editing an established profile does not reset a deliberately private choice.
    submit(alice, PATH, {'username':'PERDONPS3', 'is_public':'no'})
    submit(alice, '/account/profile/edit', {'display_name':'Renamed Alice', 'is_public':'yes'})
    assert anon.get('/players/perdonps3').status_code == 404
    assert 'value="no" checked' in alice.get(PATH).get_data(as_text=True)


def test_setup_can_be_private_and_taken_username_rolls_back_all_profile_changes(accounts):
    alice, bob = sign_in(accounts, 'alice', complete_profile=False), sign_in(accounts, 'bob', complete_profile=False)
    assert submit(alice, '/account/profile/edit', {'display_name':'Alice','username':'same_name', 'is_public':'no'}).status_code == 303
    response = submit(bob, '/account/profile/edit', {'display_name':'Bob','username':'Same_Name','bio':'Must roll back'})
    assert response.status_code == 200 and 'already taken' in response.get_data(as_text=True)
    with accounts.app_context():
        row = get_db().execute('SELECT display_name, username, is_public, bio FROM profiles WHERE id = ?', (BOB,)).fetchone()
        assert row['display_name'] == '' and row['username'] is None and not row['is_public'] and row['bio'] == ''
    assert bob.get('/library').location.endswith('/account/profile/edit')
    assert accounts.test_client().get('/players/same_name').status_code == 404
    assert submit(bob, '/account/profile/edit', {'display_name':'Bob','username':'bob_player','is_public':'no'}).status_code == 303
    assert accounts.test_client().get('/players/bob_player').status_code == 404
