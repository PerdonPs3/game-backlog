"""Public avatars require owner confirmation and obey immediate privacy revocation."""

from io import BytesIO

from PIL import Image

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


EDIT = '/account/profile/edit'
SHARING = '/account/profile/sharing'


def upload(color):
    stream = BytesIO()
    Image.new('RGB', (40, 60), color).save(stream, 'PNG')
    stream.seek(0)
    return stream, 'avatar.png'


def test_existing_private_upload_requires_confirmation_before_publication(accounts):
    alice = sign_in(accounts, 'alice')
    submit(alice, EDIT, {'display_name': 'Alice', 'photo': upload('red')})
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes'})
    anon = accounts.test_client()
    assert anon.get('/players/alice_player/photo').status_code == 404
    assert '/players/alice_player/photo' not in anon.get('/players/alice_player').get_data(as_text=True)
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes', 'publish_photo': 'yes'})
    photo = anon.get('/players/alice_player/photo')
    assert photo.status_code == 200 and photo.mimetype == 'image/jpeg'
    assert Image.open(BytesIO(photo.data)).size == (256, 256)
    assert photo.headers['Cache-Control'] == 'private, no-store'
    assert photo.headers['X-Content-Type-Options'] == 'nosniff'
    assert photo.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert photo.headers['Referrer-Policy'] == 'no-referrer'
    assert '/players/alice_player/photo' in anon.get('/players/alice_player').get_data(as_text=True)
    assert anon.get('/account/profile/photo').status_code == 401
    for url in ('/players/unknown_player/photo', '/players/ALICE_PLAYER/photo'):
        assert anon.get(url).status_code == 404


def test_editor_confirmation_replacement_removal_and_private_switch(accounts):
    alice = sign_in(accounts, 'alice')
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes'})
    submit(alice, EDIT, {'display_name': 'Alice', 'photo': upload('red'), 'publish_photo': 'yes'})
    anon = accounts.test_client()
    path = '/players/alice_player/photo'
    first = anon.get(path).data
    submit(alice, EDIT, {'display_name': 'Alice', 'photo': upload('blue'), 'publish_photo': 'yes'})
    second = anon.get(path).data
    assert first != second
    invalid = submit(alice, EDIT, {'display_name': 'Alice', 'photo': (BytesIO(b'<svg/>'), 'bad.png'), 'publish_photo': 'yes'})
    assert invalid.status_code == 200 and anon.get(path).data == second
    submit(alice, SHARING, {'username': 'alice_player', 'publish_photo': 'yes'})
    hidden = anon.get(path, headers={'If-None-Match': 'anything', 'If-Modified-Since': 'Wed, 21 Oct 2026 00:00:00 GMT'})
    assert hidden.status_code == 404 and 'no-store' in hidden.headers['Cache-Control']
    assert alice.get(path).status_code == 404
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes', 'publish_photo': 'yes'})
    assert anon.get(path).status_code == 200
    submit(alice, EDIT, {'display_name': 'Alice', 'remove_photo': 'yes', 'publish_photo': 'yes'})
    assert anon.get(path).status_code == 404
    assert path not in anon.get('/players/alice_player').get_data(as_text=True)


def test_public_photo_is_owner_scoped_and_old_photo_url_does_not_follow_renames(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes'})
    submit(bob, SHARING, {'username': 'bob_player', 'is_public': 'yes', 'publish_photo': 'yes', 'user_id': ALICE})
    submit(alice, EDIT, {'display_name': 'Alice', 'photo': upload('red')})
    anon = accounts.test_client()
    assert anon.get('/players/alice_player/photo').status_code == 404
    assert anon.get('/players/bob_player/photo').status_code == 404
    assert alice.post(EDIT, data={'display_name': 'Alice', 'publish_photo': 'yes'}).status_code == 400
    submit(alice, EDIT, {'display_name': 'Alice', 'publish_photo': 'yes'})
    assert anon.get('/players/alice_player/photo').status_code == 200
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET username_changed_at = NULL WHERE id = ?', (ALICE,))
    submit(alice, SHARING, {'username': 'renamed_player', 'is_public': 'yes'})
    assert anon.get('/players/alice_player/photo').status_code == 404
    assert anon.get('/players/renamed_player/photo').status_code == 200
    with accounts.app_context():
        assert not get_db().execute('SELECT share_photo FROM profiles WHERE id = ?', (BOB,)).fetchone()[0]


def test_public_photo_unavailable_offline(client):
    assert client.get('/players/offline_player/photo').status_code == 404
