"""Local PostgreSQL coverage for permanent milestones, banners, and privacy."""

from io import BytesIO

from PIL import Image

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_public_catalog import fake_catalog


def seed(app, owner=ALICE, count=25, completed=10):
    with app.app_context():
        db = get_db()
        for index in range(count):
            db.execute('INSERT INTO games (owner_id,title,platform,status,review) VALUES (?,?,?,?,?)',
                       (owner, f'Game {index}', 'PC', 'Completed' if index < completed else 'Backlog', 'PRIVATE NOTE'))


def keys(app, owner=ALICE):
    with app.app_context():
        return {r[0] for r in get_db().execute('SELECT badge_key FROM profile_achievements WHERE owner_id = ?', (owner,))}


def publish_profile(client, username='alice_player'):
    assert submit(client, '/account/profile/sharing', {'username': username, 'is_public': 'yes'}).status_code == 303


def image():
    output = BytesIO()
    Image.new('RGB', (900, 400), '#537d89').save(output, format='PNG')
    output.seek(0)
    return output, 'background.png'


def test_existing_progress_is_grouped_and_acknowledged_only_for_owner(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    seed(accounts)
    page = alice.get('/account/profile', follow_redirects=True).get_data(as_text=True)
    assert keys(accounts) == {'newcomer', 'collector', 'archivist', 'finisher', 'completionist'}
    assert '5 milestones' in page and 'data-achievement-notice' in page
    assert 'PRIVATE NOTE' not in page and 'profile-banner' in page
    assert 'data-achievement-notice' not in bob.get('/account/profile', follow_redirects=True).get_data(as_text=True)
    assert bob.post('/account/achievements/acknowledge', data={'badge': 'collector'}).status_code == 400
    assert submit(bob, '/account/achievements/acknowledge', {'badge': 'collector'}, source='/account/profile/edit').status_code == 200
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM profile_achievements WHERE owner_id = ? AND acknowledged_at IS NOT NULL', (ALICE,)).fetchone()[0] == 0
    selected = list(keys(accounts))
    assert submit(alice, '/account/achievements/acknowledge', {'badge': selected}, source='/account/profile/edit').status_code == 200
    assert 'data-achievement-notice' not in alice.get('/account/profile', follow_redirects=True).get_data(as_text=True)
    assert submit(alice, '/account/achievements/acknowledge', {'badge': 'creator'}, source='/account/profile/edit').status_code == 400
    with accounts.app_context():
        get_db().execute('DELETE FROM games WHERE owner_id = ?', (ALICE,))
    alice.get('/account/profile', follow_redirects=True)
    assert set(selected) == keys(accounts)


def test_save_awards_before_redirect_and_cannot_be_forged(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    result = submit(alice, '/games/new', {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Completed', 'badge_key': 'legend'}, source='/games/new?igdb_id=123')
    assert result.status_code == 302
    assert keys(accounts) == {'newcomer', 'finisher'}
    assert 'BADGES UNLOCKED' in alice.get('/library', follow_redirects=True).get_data(as_text=True)
    with accounts.app_context():
        row = get_db().execute('SELECT relrowsecurity FROM pg_class WHERE relnamespace = current_schema()::regnamespace AND relname = ?', ('profile_achievements',)).fetchone()
        assert row[0]


def test_one_save_can_unlock_collection_completion_and_published_review(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    seed(accounts, count=9, completed=9)
    publish_profile(alice)
    assert submit(alice, '/account/achievements/acknowledge', {'badge': ['newcomer', 'finisher']}, source='/account/profile/edit').status_code == 200
    result = submit(alice, '/games/new', {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC',
                    'status': 'Completed', 'rating': '9', 'review': 'A public opinion.', 'publish_review': 'yes'},
                    source='/games/new?igdb_id=123')
    assert result.status_code == 303
    assert keys(accounts) == {'newcomer', 'collector', 'finisher', 'completionist', 'reviewer'}
    page = alice.get(result.location).get_data(as_text=True)
    assert 'data-achievement-notice' in page and '3 milestones' in page


def test_review_milestones_exclude_library_notes_and_moderated_reviews(accounts):
    alice = sign_in(accounts, 'alice')
    seed(accounts, count=1, completed=0)
    alice.get('/account/profile', follow_redirects=True)
    assert keys(accounts) == {'newcomer'}
    with accounts.app_context():
        db = get_db()
        for index in range(10):
            db.execute('INSERT INTO public_game_reviews (owner_id,catalog_id,rating,body,moderation_hidden) VALUES (?,?,9,?,?)', (ALICE, index + 1, 'Published words', index == 9))
    alice.get('/account/profile', follow_redirects=True)
    assert 'reviewer' in keys(accounts) and 'critic' not in keys(accounts)
    with accounts.app_context():
        get_db().execute('UPDATE public_game_reviews SET moderation_hidden = FALSE WHERE owner_id = ?', (ALICE,))
    alice.get('/account/profile', follow_redirects=True)
    assert 'critic' in keys(accounts)


def test_featured_badges_are_earned_bounded_private_and_legacy_forms_preserve_them(accounts):
    alice = sign_in(accounts, 'alice')
    seed(accounts)
    publish_profile(alice)
    payload = {'display_name': 'Alice', 'badge_controls': 'yes', 'featured_badges': ['archivist', 'completionist'], 'share_badges': 'yes'}
    assert submit(alice, '/account/profile/edit', payload).status_code == 303
    public = accounts.test_client().get('/profile/alice_player').get_data(as_text=True)
    assert 'Featured · 2/3' in public and 'achievement-progress' not in public
    assert 'data-achievement-notice' not in public and 'PRIVATE NOTE' not in public
    for selection in (['legend'], ['newcomer'] * 2, ['newcomer', 'collector', 'archivist', 'finisher']):
        bad = submit(alice, '/account/profile/edit', {**payload, 'display_name': 'Rejected', 'featured_badges': selection})
        assert bad.status_code == 200 and 'Choose up to three' in bad.get_data(as_text=True)
        with accounts.app_context():
            assert get_db().execute('SELECT display_name FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0] == 'Alice'
    assert submit(alice, '/account/profile/edit', {**payload, 'share_badges': 'no'}).status_code == 303
    assert 'id="badges"' not in accounts.test_client().get('/profile/alice_player').get_data(as_text=True)
    assert submit(alice, '/account/profile/edit', {'display_name': 'Alice'}).status_code == 303
    with accounts.app_context():
        assert not get_db().execute('SELECT share_badges FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0]


def test_background_is_normalized_owner_scoped_and_revoked_immediately(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    publish_profile(alice)
    payload = {'display_name': 'Alice', 'background_controls': 'yes', 'background_key': 'castle', 'share_background': 'yes'}
    assert submit(alice, '/account/profile/edit', {**payload, 'background': image()}).status_code == 303
    photo = alice.get('/account/profile/background')
    assert photo.status_code == 200 and photo.mimetype == 'image/jpeg'
    with Image.open(BytesIO(photo.data)) as decoded:
        assert decoded.size == (1600, 600) and not decoded.getexif()
    assert bob.get('/account/profile/background').status_code == 404
    visitor = accounts.test_client()
    assert visitor.get('/account/profile/background').status_code == 404
    banner = visitor.get('/players/alice_player/background')
    assert banner.data == photo.data and 'no-store' in banner.headers['Cache-Control']
    assert banner.headers['X-Content-Type-Options'] == 'nosniff'
    assert submit(alice, '/account/profile/edit', {**payload, 'background_key': 'custom', 'share_background': 'no'}).status_code == 303
    assert visitor.get('/players/alice_player/background').status_code == 404
    assert 'background-obsidian' in visitor.get('/profile/alice_player').get_data(as_text=True)
    assert submit(alice, '/account/profile/edit', {**payload, 'background_key': 'custom'}).status_code == 303
    submit(alice, '/account/profile/sharing', {'username': 'alice_player'})
    assert visitor.get('/players/alice_player/background').status_code == 404
    assert alice.get('/account/profile/background').status_code == 200
    assert submit(alice, '/account/profile/edit', {**payload, 'background_key': 'custom', 'remove_background': 'yes'}).status_code == 303
    assert alice.get('/account/profile/background').status_code == 404


def test_invalid_background_preserves_profile_and_all_settings(accounts):
    alice = sign_in(accounts, 'alice')
    payload = {'display_name': 'Rejected', 'background_controls': 'yes', 'background_key': 'castle', 'share_background': 'yes'}
    for changes in ({'background_key': 'url(evil)'}, {'background_key': 'custom'}, {'background': (BytesIO(b'<svg></svg>'), 'fake.png')}, {'background': (BytesIO(b'x' * (2 * 1024 * 1024 + 1)), 'large.jpg')}):
        assert submit(alice, '/account/profile/edit', {**payload, **changes}).status_code == 200
        with accounts.app_context():
            assert tuple(get_db().execute('SELECT display_name,background_key,background_image FROM profiles WHERE id = ?', (ALICE,)).fetchone()) == ('Alice', 'castle', None)
