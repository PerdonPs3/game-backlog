"""Real PostgreSQL relationship and privacy boundaries using fictional accounts."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_game_reviews import public_author
from tests.test_public_catalog import fake_catalog


@pytest.fixture
def players(accounts):
    return public_author(accounts, 'alice'), public_author(accounts, 'bob')


def change(client, username='bob_player', action='follow', **data):
    return submit(client, f'/connections/{username}/{action}', data, source='/account/connections')


def row(app, statement, params=()):
    with app.app_context():
        return get_db().execute(statement, params).fetchone()


def execute(app, statement, params=()):
    with app.app_context():
        get_db().execute(statement, params)


def test_public_follow_is_idempotent_and_self_follow_is_rejected(accounts, players):
    alice, bob = players
    for _ in range(2):
        assert change(alice).status_code == 303
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 1
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'accepted'
    assert b'Following @bob_player' in alice.get('/profile/bob_player').data
    assert b'Unfollow' in alice.get('/profile/bob_player').data
    assert change(alice, 'alice_player').status_code == 400
    assert change(alice, action='unfollow').status_code == 303
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


def test_private_request_approval_never_opens_private_profile(accounts, players):
    alice, bob = players
    execute(accounts, 'UPDATE profiles SET is_public = FALSE WHERE id = ?', (BOB,))
    response = submit(alice, '/account/connections/follow', {'username': '@BOB_PLAYER'}, source='/account/connections')
    assert response.status_code == 303
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'pending'
    assert b'@bob_player' in alice.get('/account/connections?view=sent').data
    assert b'Approve' in bob.get('/account/connections?view=requests').data
    assert change(alice, action='approve').status_code == 303  # Cannot approve your outgoing request.
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'pending'
    assert change(bob, 'alice_player', 'approve').status_code == 303
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'accepted'
    assert alice.get('/profile/bob_player').status_code == 404
    assert b'Private player' in alice.get('/account/connections?view=following').data
    assert b'@bob_player' in alice.get('/account/connections?view=following').data
    assert change(bob, 'alice_player', 'remove').status_code == 303
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


@pytest.mark.parametrize('action,actor', [('cancel', 'alice'), ('decline', 'bob')])
def test_pending_request_can_be_cancelled_or_declined(accounts, players, action, actor):
    alice, bob = players
    execute(accounts, 'UPDATE profiles SET is_public = FALSE WHERE id = ?', (BOB,))
    change(alice)
    change(alice if actor == 'alice' else bob, 'bob_player' if actor == 'alice' else 'alice_player', action)
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


def test_private_unknown_and_blocked_targets_have_the_same_follow_feedback(accounts, players):
    alice, bob = players
    execute(accounts, 'UPDATE profiles SET is_public = FALSE WHERE id = ?', (BOB,))
    responses = []
    for username in ('bob_player', 'missing_player'):
        response = change(alice, username)
        responses.append((response.status_code, response.location))
        assert b'Follow request saved if this player is available.' in alice.get(response.location).data
    change(bob, 'alice_player', 'block')
    response = change(alice)
    responses.append((response.status_code, response.location))
    assert len(set(responses)) == 1
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


def test_sharing_defaults_private_and_public_counts_exclude_private_members(accounts, players):
    alice, bob = players
    change(alice)
    anonymous = accounts.test_client()
    path = '/profile/bob_player/connections/followers'
    assert anonymous.get(path).status_code == 404
    assert row(accounts, 'SELECT share_connections FROM profiles WHERE id = ?', (BOB,))[0] is False
    response = submit(bob, '/account/profile/sharing', {'username': 'bob_player', 'is_public': 'yes',
                      'connection_privacy_controls': 'yes', 'share_connections': 'yes'})
    assert response.status_code == 303
    shared = anonymous.get(path)
    assert shared.status_code == 200 and b'@alice_player' in shared.data
    for secret in (ALICE, BOB, 'alice@example.test', 'alice-access', 'alice-refresh'):
        assert secret.encode() not in shared.data
    execute(accounts, 'UPDATE profiles SET is_public = FALSE WHERE id = ?', (ALICE,))
    assert b'@alice_player' not in anonymous.get(path).data
    assert b'<strong>0</strong> followers' in anonymous.get('/profile/bob_player').data
    assert b'@alice_player' in bob.get('/account/connections?view=followers').data
    # Legacy forms preserve sharing; a new opt-out revokes it immediately.
    submit(bob, '/account/profile/sharing', {'username': 'bob_player', 'is_public': 'yes'})
    assert anonymous.get(path).status_code == 200
    submit(bob, '/account/profile/sharing', {'username': 'bob_player', 'is_public': 'yes', 'connection_privacy_controls': 'yes'})
    assert anonymous.get(path).status_code == 404


def test_privatizing_keeps_accepted_connections_and_does_not_auto_approve(accounts, players):
    alice, bob = players
    change(alice)
    execute(accounts, 'UPDATE profiles SET is_public = FALSE WHERE id = ?', (BOB,))
    assert alice.get('/profile/bob_player').status_code == 404
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'accepted'
    change(alice, action='unfollow')
    change(alice)
    execute(accounts, 'UPDATE profiles SET is_public = TRUE WHERE id = ?', (BOB,))
    change(alice)
    assert row(accounts, 'SELECT state FROM player_follows')[0] == 'pending'


def test_block_removes_both_directions_and_hides_public_surfaces(accounts, players):
    alice, bob = players
    fake_catalog(accounts)
    change(alice)
    change(bob, 'alice_player')
    execute(accounts, "UPDATE profiles SET avatar_image = ?, share_photo = TRUE, share_connections = TRUE, background_key = 'custom', background_image = ?, share_background = TRUE WHERE id = ?", (b'photo', b'background', BOB))
    execute(accounts, 'INSERT INTO public_game_reviews (owner_id,catalog_id,rating,body) VALUES (?,123,8,?)', (BOB, 'BOB PUBLIC REVIEW'))
    assert change(alice, action='block').status_code == 303
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0
    for viewer, username in ((alice, 'bob_player'), (bob, 'alice_player')):
        assert viewer.get('/profile/' + username).status_code == 404
        assert ('@' + username).encode() not in viewer.get('/players?q=' + username).data
    for path in ('/players/bob_player', '/players/bob_player/photo', '/players/bob_player/background',
                 '/profile/bob_player/wishlist', '/profile/bob_player/connections/followers'):
        assert alice.get(path).status_code == 404
    assert b'BOB PUBLIC REVIEW' not in alice.get('/explore/games/123').data
    assert b'BOB PUBLIC REVIEW' in accounts.test_client().get('/explore/games/123').data
    assert accounts.test_client().get('/profile/bob_player').status_code == 200
    change(bob, 'alice_player')
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0
    change(bob, 'alice_player', 'block')
    change(alice, action='unblock')
    assert alice.get('/profile/bob_player').status_code == 404  # The other player's block remains.
    change(bob, 'alice_player', 'unblock')
    assert alice.get('/profile/bob_player').status_code == 200
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


def test_rename_preserves_relationships_but_alias_cannot_bypass_block(accounts, players):
    alice, bob = players
    change(alice)
    execute(accounts, 'UPDATE profiles SET username_changed_at = NULL WHERE id = ?', (BOB,))
    submit(bob, '/account/profile/sharing', {'username': 'bob_renamed', 'is_public': 'yes'})
    assert b'@bob_renamed' in alice.get('/account/connections?view=following').data
    change(alice, 'bob_renamed', 'block')
    assert alice.get('/profile/bob_player').status_code == 404
    assert alice.get('/players/bob_player').status_code == 404
    change(alice, 'bob_player')
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


def test_new_follow_attempt_budget_does_not_prevent_blocking_or_cancelling(accounts, players):
    alice, _ = players
    accounts.config['FOLLOW_REQUEST_LIMIT'] = 2
    assert change(alice).status_code == 303
    assert change(alice, 'missing_player').status_code == 303
    response = change(alice)
    assert response.status_code == 429 and response.headers['Retry-After'] == '3600'
    assert change(alice, action='cancel').status_code == 303
    assert change(alice, action='block').status_code == 303


@pytest.mark.parametrize('path', ['/account/connections', '/connections/bob_player/follow'])
def test_session_and_csrf_boundaries(accounts, players, path):
    alice, _ = players
    if path == '/account/connections':
        assert accounts.test_client().get(path).status_code == 302
    else:
        assert alice.post(path).status_code == 400
        assert alice.get(path).status_code == 405
    with alice.session_transaction() as session:
        from app.auth import fingerprint
        opaque = session['account_session']
    execute(accounts, 'UPDATE account_sessions SET recovery = 1 WHERE id_hash = ?', (fingerprint(opaque),))
    assert alice.get('/account/connections').location.endswith('/account/password')
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0


@pytest.mark.parametrize('page', ['0', '-1', '10001', 'invalid'])
def test_list_pagination_rejects_invalid_bounds(players, page):
    alice, _ = players
    assert alice.get('/account/connections?page=' + page).status_code == 400


def test_public_pagination_is_bounded_and_private_requests_never_leak(accounts, players):
    alice, bob = players
    with accounts.app_context():
        db = get_db()
        for index in range(23):
            owner = str(uuid4())
            username = f'friend_{index:02d}'
            db.execute('INSERT INTO profiles (id, display_name, is_public) VALUES (?, ?, FALSE)', (owner, username))
            db.execute('INSERT INTO profile_usernames (username, owner_id) VALUES (?, ?)', (username, owner))
            db.execute('UPDATE profiles SET username = ?, is_public = TRUE WHERE id = ?', (username, owner))
            db.execute("INSERT INTO player_follows (follower_id, followed_id, state) VALUES (?, ?, 'accepted')", (owner, BOB))
        db.execute('UPDATE profiles SET share_connections = TRUE WHERE id = ?', (BOB,))
    path = '/profile/bob_player/connections/followers'
    anon = accounts.test_client()
    assert anon.get(path).data.count(b'class="connection-card"') == 20
    assert anon.get(path + '?page=2').data.count(b'class="connection-card"') == 3
    assert anon.get(path + '?page=3').status_code == 404
    assert anon.get('/profile/bob_player/connections/requests').status_code == 404
    response = anon.get(path)
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert 'Cookie' in response.headers['Vary']


def test_concurrent_follow_and_block_cannot_leave_a_relationship(accounts, players):
    # Exercise real row locks using independent sessions and connections.
    alice, bob = players
    another_alice = sign_in(accounts, 'alice')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda task: change(*task).status_code,
                                [(another_alice, 'bob_player', 'follow'), (bob, 'alice_player', 'block')]))
    assert results == [303, 303]
    assert row(accounts, 'SELECT COUNT(*) FROM player_follows')[0] == 0
    assert row(accounts, 'SELECT COUNT(*) FROM player_blocks')[0] == 1
