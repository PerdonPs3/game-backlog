"""Quick additions retain ordinary validation and account ownership."""

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_public_catalog import fake_catalog


def test_quick_add_stays_on_the_game_and_only_lists_the_current_owners_entries(accounts):
    fake_catalog(accounts)
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    path = '/explore/games/123'
    data = {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC',
            'status': 'Playing', 'rating': '9', 'return_to_catalog': 'yes'}
    assert alice.post('/games/new', data=data).status_code == 303
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
    response = submit(alice, '/games/new', data, source=path)
    assert response.status_code == 303
    assert response.location == path + '#library-actions'
    own = alice.get(response.location).get_data(as_text=True)
    assert 'Added to your library.' in own and 'data-status="Playing">Playing' in own
    assert 'aria-label="Your rating: 4.5/5"' in own
    assert '<option value="PC">' not in own
    assert '<option value="PS3">' in own
    other = bob.get(path).get_data(as_text=True)
    assert 'aria-label="Your rating: 4.5/5"' not in other and '<option value="PC">' in other
    anonymous = accounts.test_client().get(path).get_data(as_text=True)
    assert 'aria-label="Your rating: 4.5/5"' not in anonymous and 'catalog-quick-form' not in anonymous
    assert 'Sign in to add game' in anonymous
    duplicate = submit(alice, '/games/new', data, source=path)
    assert b'already in your collection' in duplicate.data
    assert submit(bob, '/games/new', data, source=path).status_code == 303
    with accounts.app_context():
        rows = get_db().execute('SELECT owner_id, rating FROM games ORDER BY id').fetchall()
        assert [(str(row['owner_id']), row['rating']) for row in rows] == [(ALICE, 9), (BOB, 9)]


def test_quick_add_revalidates_platform_rating_and_catalog_title(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    data = {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC',
            'status': 'Backlog', 'return_to_catalog': 'yes'}
    for changes in ({'platform': 'Invalid'}, {'rating': '11'}, {'rating': '4.5'}, {'title': 'Fake title'}):
        response = submit(client, '/games/new', {**data, **changes}, source='/explore/games/123')
        assert response.status_code == 200 and b'role="alert"' in response.data
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0


def test_star_ratings_display_five_stars_preserve_saved_precision_and_can_be_cleared(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    data = {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Completed', 'rating': '7'}
    assert submit(client, '/games/new', data, source='/games/new?igdb_id=123').status_code == 302
    with accounts.app_context():
        game_id = get_db().execute('SELECT id FROM games').fetchone()[0]
    path = f'/games/{game_id}/edit'
    page = client.get(path).get_data(as_text=True)
    assert '3.5 out of 5 stars" checked' in page
    assert submit(client, path, {**data, 'rating': ''}).status_code == 302
    with accounts.app_context():
        assert get_db().execute('SELECT rating FROM games WHERE id = ?', (game_id,)).fetchone()[0] is None


def test_header_search_is_available_from_private_pages_and_submits_to_public_catalog(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    for path in ('/library', '/account/profile/edit', '/account/profile', '/games/new', '/explore/games/123'):
        page = client.get(path, follow_redirects=True)
        assert page.status_code == 200
        assert b'class="header-search" action="/explore"' in page.data
    assert b'Portal 2' in client.get('/explore?q=Portal').data
