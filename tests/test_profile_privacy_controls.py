import re

from app.db import get_db
from tests.test_accounts import ALICE, accounts, sign_in, submit


FIELDS = ('is_public', 'share_bio', 'share_showcase', 'share_photo', 'share_statistics',
          'share_activity', 'share_connections', 'share_wishlist', 'share_background', 'share_badges')
PAYLOAD = {'display_name': 'Alice', 'username': 'alice_player', 'profile_sharing': 'yes',
           'profile_privacy_controls': 'yes', 'background_controls': 'yes', 'background_key': 'castle',
           'badge_controls': 'yes'}


def values(app):
    with app.app_context():
        return tuple(get_db().execute('SELECT ' + ','.join(FIELDS) + ' FROM profiles WHERE id = ?', (ALICE,)).fetchone())


def checked(html, name):
    return 'checked' in re.search(r'<input[^>]*name="' + name + r'"[^>]*>', html).group()


def test_new_profile_defaults_public_with_no_hide_switches_enabled(accounts):
    client = sign_in(accounts, 'alice', complete_profile=False)
    html = client.get('/settings/profile').text
    for control in ('private_profile', 'hide_bio', 'hide_photo', 'hide_background', 'hide_showcase',
                    'hide_statistics', 'hide_activity', 'hide_connections', 'private_wishlist', 'hide_badges'):
        assert not checked(html, control)
    assert submit(client, '/settings/profile', PAYLOAD).status_code == 303
    assert all(values(accounts))
    assert accounts.test_client().get('/players/alice_player').status_code == 200
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_hide_switches_persist_and_private_profile_keeps_section_preferences(accounts):
    client = sign_in(accounts, 'alice', complete_profile=False)
    submit(client, '/settings/profile', PAYLOAD)
    hidden = {**PAYLOAD, 'hide_bio': 'yes', 'hide_photo': 'yes', 'hide_connections': 'yes',
              'hide_background': 'yes', 'hide_badges': 'yes', 'private_wishlist': 'yes'}
    assert submit(client, '/settings/profile', hidden).status_code == 303
    expected = (True, False, True, False, True, True, False, False, False, False)
    assert values(accounts) == expected
    html = client.get('/settings/profile').text
    for control in ('hide_bio', 'hide_photo', 'hide_connections', 'hide_background', 'hide_badges', 'private_wishlist'):
        assert checked(html, control)
    assert not checked(html, 'hide_activity')
    assert submit(client, '/settings/profile', {**hidden, 'private_profile': 'yes'}).status_code == 303
    assert accounts.test_client().get('/players/alice_player').status_code == 404
    assert values(accounts)[1:] == expected[1:]
    assert submit(client, '/settings/profile', hidden).status_code == 303
    assert values(accounts) == expected


def test_editor_preserves_existing_choices_and_failed_submissions(accounts):
    client = sign_in(accounts, 'alice')
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET share_statistics = FALSE, share_photo = FALSE, share_connections = FALSE WHERE id = ?', (ALICE,))
    before = values(accounts)
    html = client.get('/settings/profile').text
    assert checked(html, 'hide_statistics') and checked(html, 'hide_photo') and checked(html, 'hide_connections')
    assert values(accounts) == before
    response = submit(client, '/settings/profile', {**PAYLOAD, 'display_name': '', 'hide_statistics': 'yes'})
    assert response.status_code == 200
    assert checked(response.text, 'hide_statistics')
    assert not checked(response.text, 'hide_photo')
    assert values(accounts) == before


def test_hide_photo_revokes_public_image_without_deleting_the_upload(accounts):
    from tests.test_profile_achievements import image
    client = sign_in(accounts, 'alice', complete_profile=False)
    assert submit(client, '/settings/profile', {**PAYLOAD, 'photo': image()}).status_code == 303
    visitor = accounts.test_client()
    public = '/players/alice_player/photo'
    original = visitor.get(public)
    assert original.status_code == 200
    assert submit(client, '/settings/profile', {**PAYLOAD, 'hide_photo': 'yes'}).status_code == 303
    assert visitor.get(public).status_code == 404
    assert client.get('/account/profile/photo').data == original.data
    assert submit(client, '/settings/profile', PAYLOAD).status_code == 303
    assert visitor.get(public).data == original.data
