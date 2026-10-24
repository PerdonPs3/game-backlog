from time import time
from app.db import get_db
from app.auth import fingerprint, SESSION_SECONDS
from tests.test_accounts import accounts, sign_in, submit, ALICE, BOB
from tests.test_public_catalog import fake_catalog


def test_browser_remembers_login_and_logout_revokes_copied_cookie(accounts):
    client = sign_in(accounts, 'alice')
    with client.session_transaction() as cookie:
        assert cookie.permanent
        opaque = cookie['account_session']
    stored_cookie = client.get_cookie('session')
    assert stored_cookie.expires is not None and stored_cookie.http_only
    assert stored_cookie.expires.timestamp() > time() + 29 * 86400
    returning_browser = accounts.test_client()
    returning_browser.set_cookie('session', stored_cookie.value)
    assert returning_browser.get('/library').status_code == 200
    with accounts.app_context():
        row = get_db().execute('SELECT valid_until FROM account_sessions WHERE id_hash = ?', (fingerprint(opaque),)).fetchone()
        assert row[0] > time() + SESSION_SECONDS - 60
    submit(client, '/account/logout', {}, source='/account/profile/edit')
    assert returning_browser.get('/library').location == '/account/login'


def test_one_profile_address_has_owner_controls_and_minimal_visitor_projection(accounts):
    owner = sign_in(accounts, 'alice', complete_profile=False)
    result = submit(owner, '/account/profile/edit', {'display_name': 'Alice', 'username': 'alice_player', 'bio': 'A public bio', 'profile_sharing': 'yes', 'is_public': 'yes', 'share_bio': 'yes', 'share_showcase': 'yes', 'share_photo': 'yes'})
    assert result.status_code == 303 and result.location == '/profile/alice_player#profile-feedback'
    assert 'Edit profile' in owner.get('/profile/alice_player').text
    visitor = accounts.test_client()
    public = visitor.get('/profile/alice_player')
    assert public.status_code == 200 and 'A public bio' in public.text
    assert 'Edit profile' not in public.text and 'Your private workspace' not in public.text
    assert 'alice@example.test' not in public.text
    other = sign_in(accounts, 'bob')
    assert 'Edit profile' not in other.get('/profile/alice_player').text
    assert other.post('/profile/alice_player', data={}).status_code in (400, 405)
    submit(owner, '/account/alice_player/profile/edit', {'display_name': 'Alice', 'username': 'alice_player', 'profile_sharing': 'yes', 'is_public': 'no'})
    assert visitor.get('/profile/alice_player').status_code == 404
    assert other.get('/profile/alice_player').status_code == 404
    assert 'Edit profile' in owner.get('/profile/alice_player').text


def test_editor_combines_sharing_and_preserves_existing_private_choices(accounts):
    owner = sign_in(accounts, 'alice', complete_profile=False)
    page = owner.get('/account/profile/edit').text
    assert 'Privacy &amp; sharing' in page
    for field in ('share_bio', 'share_showcase', 'share_photo'):
        assert f'name="{field}" value="yes" checked' in page
    submit(owner, '/account/profile/edit', {'display_name': 'Alice', 'username': 'alice_player', 'profile_sharing': 'yes', 'is_public': 'no'})
    with accounts.app_context():
        profile = get_db().execute('SELECT is_public, share_bio, share_showcase, share_photo FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert not any(profile)
    submit(owner, '/account/alice_player/profile/edit', {'display_name': 'Alice changed'})
    with accounts.app_context():
        assert not any(get_db().execute('SELECT is_public, share_bio, share_showcase, share_photo FROM profiles WHERE id = ?', (ALICE,)).fetchone())
    denied = submit(owner, '/account/alice_player/profile/edit', {'display_name': 'Not saved', 'username': 'another_name', 'profile_sharing': 'yes', 'is_public': 'yes', 'share_bio': 'yes'})
    assert denied.status_code == 200 and 'change your username again' in denied.text
    assert 'value="alice_player"' in denied.text
    with accounts.app_context():
        profile = get_db().execute('SELECT display_name, is_public, share_bio FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert profile['display_name'] == 'Alice changed' and not profile['is_public'] and not profile['share_bio']
    response = owner.get('/account/alice_player/profile/sharing')
    assert response.location == '/account/alice_player/profile/edit#profile-privacy'


def test_quick_add_recovers_from_stale_csrf_without_saving_and_refreshes_tokens(accounts):
    fake_catalog(accounts)
    owner = sign_in(accounts, 'alice')
    assert accounts.test_client().get('/account/form-token').status_code == 401
    token = owner.get('/account/form-token')
    assert token.status_code == 200 and token.json['csrf_token']
    assert token.headers['Cache-Control'] == 'private, no-store'
    invalid = owner.post('/games/new', data={'return_to_catalog': 'yes', 'igdb_id': '123', 'csrf_token': 'stale'})
    assert invalid.status_code == 303 and invalid.location == '/explore/games/123#library-actions'
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
    result = owner.post('/games/new', data={'csrf_token': owner.get('/account/form-token').json['csrf_token'], 'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Backlog', 'return_to_catalog': 'yes'})
    assert result.status_code == 303
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games WHERE owner_id = ?', (ALICE,)).fetchone()[0] == 1


def test_https_quick_add_keeps_same_origin_referer_and_rejects_foreign_origin(accounts):
    import re
    fake_catalog(accounts)
    owner = sign_in(accounts, 'alice')
    page = owner.get('/explore/games/123', base_url='https://localhost')
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    # Emulate a browser following the response policy, rather than hand-waving
    # the HTTPS-only Referer requirement away in the test environment.
    headers = {'Referer': 'https://localhost/explore/games/123'} if page.headers['Referrer-Policy'] == 'same-origin' else {}
    data = {'csrf_token': token, 'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Backlog', 'return_to_catalog': 'yes'}
    saved = owner.post('/games/new', data=data, headers=headers, base_url='https://localhost')
    assert saved.status_code == 303
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games WHERE owner_id = ?', (ALICE,)).fetchone()[0] == 1
    owner.post('/games/new', data={**data, 'platform': 'PS3'}, headers={'Referer': 'https://evil.example/'}, base_url='https://localhost')
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games WHERE owner_id = ?', (ALICE,)).fetchone()[0] == 1
