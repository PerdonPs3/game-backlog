"""Canonical navigation, safe returns and public/private game boundaries."""

from urllib.parse import parse_qs, urlsplit

import pytest

from app.catalog import CatalogError
from app.db import get_db
from app.navigation import game_url, safe_destination
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_public_catalog import fake_catalog


def seed(app, owner, platform='PC', catalog_id=123, notes='PRIVATE NOTES'):
    with app.app_context():
        return get_db().execute("INSERT INTO games (owner_id,igdb_id,title,platform,status,rating,review) VALUES (?,?,'Portal 2',?,'Playing',9,?) RETURNING id", (owner,catalog_id,platform,notes)).fetchone()[0]


def test_library_and_profiles_have_stable_owner_scoped_addresses(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    seed(accounts,ALICE)
    page = alice.get('/library')
    assert page.status_code == 200
    assert 'Library</a>' in page.text and 'Community</a>' in page.text
    assert '/library/wishlist' in page.text and '/library/lists' in page.text
    assert 'data-game-details' not in page.text and 'game-details-dialog' not in page.text
    assert '/games/123/portal-2' in page.text
    assert alice.get('/settings/profile').status_code == 200
    assert alice.get('/settings/data').status_code == 200


def test_one_game_page_combines_public_information_and_only_the_viewers_progress(accounts):
    fake_catalog(accounts)
    alice, bob = sign_in(accounts,'alice'), sign_in(accounts,'bob')
    pc = seed(accounts,ALICE,'PC',notes='ALICE PC PRIVATE')
    ps3 = seed(accounts,ALICE,'PS3',notes='ALICE PS3 PRIVATE')
    seed(accounts,BOB,notes='BOB PRIVATE')
    page = alice.get('/games/123/portal-2')
    assert page.status_code == 200 and 'Your progress' in page.text
    assert 'ALICE PC PRIVATE' in page.text and 'ALICE PS3 PRIVATE' in page.text
    assert 'BOB PRIVATE' not in page.text
    assert f'/library/entries/{pc}/edit' in page.text and f'/library/entries/{ps3}/edit' in page.text
    other = bob.get('/games/123/portal-2')
    assert 'BOB PRIVATE' in other.text and 'ALICE PC PRIVATE' not in other.text
    anonymous = accounts.test_client().get('/games/123/portal-2')
    assert anonymous.status_code == 200 and 'PRIVATE' not in anonymous.text
    assert 'id="your-progress"' not in anonymous.text
    assert page.headers['Cache-Control'] == 'private, no-store'


def test_legacy_numeric_entry_id_cannot_be_mistaken_for_catalog_identity(accounts):
    fake_catalog(accounts)
    alice, bob = sign_in(accounts,'alice'), sign_in(accounts,'bob')
    entry = seed(accounts,ALICE)
    old = alice.get(f'/games/{entry}')
    assert old.status_code == 302 and '/games/123/portal-2' in old.location
    assert old.location.endswith('#your-progress')
    assert bob.get(f'/games/{entry}').status_code == 404
    assert accounts.test_client().get(f'/games/{entry}').location.endswith('/account/login')
    public = accounts.test_client().get('/explore/games/123')
    assert public.status_code == 302 and public.location == '/games/123/portal-2'


def test_manual_entries_and_catalog_outages_keep_owner_notes_accessible(accounts):
    catalog = fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    manual = seed(accounts,ALICE,catalog_id=None,notes='MANUAL PRIVATE')
    assert 'MANUAL PRIVATE' in alice.get(f'/library/entries/{manual}').text
    seed(accounts,ALICE,notes='SAVED PRIVATE')
    catalog.get_game.side_effect = CatalogError('upstream-secret')
    owner = alice.get('/games/123/portal-2')
    assert owner.status_code == 200 and 'SAVED PRIVATE' in owner.text
    assert 'upstream-secret' not in owner.text
    outsider = accounts.test_client().get('/games/123/portal-2')
    assert outsider.status_code == 503 and 'SAVED PRIVATE' not in outsider.text


@pytest.mark.parametrize('value', ['https://evil.example', '//evil.example', '//[invalid', '/account/logout', '/not-real', '/library\\evil', '/library?'+ '&'.join('q=x' for _ in range(32))])
def test_return_context_rejects_external_actions_and_unbounded_queries(app,value):
    with app.test_request_context('/'):
        assert safe_destination(value) is None


def test_game_links_and_edit_cancel_preserve_the_source_filters(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    entry = seed(accounts,ALICE)
    origin = '/discover?mode=popular&genre=Puzzle&platform=6&page=2'
    with accounts.test_request_context('/discover?mode=popular&genre=Puzzle&platform=6&page=2'):
        target = game_url(123,'Portal 2')
    assert parse_qs(urlsplit(target).query)['from'] == [origin]
    page = alice.get(f'/library/entries/{entry}/edit', query_string={'from':origin})
    assert page.status_code == 200 and 'name="return_path"' in page.text
    assert 'mode=popular&amp;genre=Puzzle&amp;platform=6&amp;page=2' in page.text
    saved = submit(alice,f'/library/entries/{entry}/edit',
                   {'title':'Portal 2','platform':'PC','status':'Completed','rating':'9','review':'Retained', 'return_path':origin})
    assert saved.status_code == 302 and saved.location == origin
    forged = submit(alice,f'/library/entries/{entry}/edit',
                   {'title':'Portal 2','platform':'PC','status':'Completed','rating':'9','return_path':'https://evil.example'})
    assert forged.status_code == 302 and forged.location.startswith('/games/123/portal-2')


def test_old_private_aliases_redirect_but_never_grant_other_users_access(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    with accounts.app_context():
        from app.public_profiles import claim_username
        db=get_db();claim_username(db,ALICE,'alice_player')
        db.execute("UPDATE profiles SET username='alice_player' WHERE id=?",(ALICE,))
    old=alice.get('/account/alice_player/library?q=Portal')
    assert old.status_code == 302 and old.location == '/library?q=Portal'
    assert alice.get('/account/bob_player/library').status_code == 404
    assert alice.get('/account/profile/edit').location == '/settings/profile'


def test_sign_in_resumes_the_private_page_and_ignores_external_destinations(accounts):
    sign_in(accounts, 'alice')
    client = accounts.test_client()
    target = '/library/wishlist?q=Portal&page=1'
    assert client.get(target).location.endswith('/account/login')
    result = submit(client, '/account/login', {'email':'alice@example.test','password':'test-password'})
    assert result.location == target
    forged = accounts.test_client()
    with forged.session_transaction() as saved:
        from time import time
        saved['navigation_login'] = {'path':'https://evil.example', 'at':int(time())}
    result = submit(forged, '/account/login', {'email':'alice@example.test','password':'test-password'})
    assert result.location == '/library'


def test_wishlist_save_retains_validated_discover_context(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    target = '/discover?mode=popular&genre=Puzzle&page=2'
    result = submit(alice,'/wishlist/games/123/add',{'return_path':target},source='/games/123/portal-2')
    assert result.status_code == 303 and result.location == target
    forged = submit(alice,'/wishlist/games/123/remove',{'return_path':'//evil.example'},source='/library/wishlist')
    assert forged.status_code == 303 and forged.location == '/library/wishlist'


@pytest.mark.parametrize('path', ['/library', '/library/wishlist', '/library/lists', '/library/pick'])
def test_library_tabs_share_one_heading_toolbar_and_owner_scoped_counter(accounts, path):
    from tests.test_library_layout import LibraryParser
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    sign_in(accounts,'bob')
    seed(accounts,ALICE)
    seed(accounts,BOB,notes='OTHER PRIVATE')
    page = alice.get(path)
    assert page.status_code == 200
    parser = LibraryParser(); parser.feed(page.text)
    assert sum(tag == 'h1' for tag, _ in parser.tags) == 1
    assert 'class="library-wordmark"' in page.text
    assert 'library-section-page' in page.text and page.text.count('class="library-heading"') == 1
    assert any(tag == 'a' and attrs.get('href') == path and attrs.get('aria-current') == 'page' for tag,attrs in parser.tags)
    assert any(attrs.get('id') == 'collection-count' and attrs.get('aria-label') == '1 game' for _,attrs in parser.tags)
    assert 'OTHER PRIVATE' not in page.text
    assert page.text.index('class="library-heading"') < page.text.index('id="game-collection"' if path == '/library' else 'class="workspace-body"')


def test_library_tabs_carry_filters_without_accepting_external_or_foreign_origins(accounts):
    from tests.test_library_layout import LibraryParser
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    sign_in(accounts,'bob')
    with accounts.app_context():
        foreign = get_db().execute("INSERT INTO game_lists (name,name_key,owner_id) VALUES ('Private','private',?) RETURNING id", (BOB,)).fetchone()[0]
    root = '/library?q=Portal&status=Playing&sort=rating'
    page = alice.get('/library/wishlist',query_string={'from':root})
    parser = LibraryParser();parser.feed(page.text)
    links = [attrs for tag,attrs in parser.tags if tag == 'a']
    assert any(attrs.get('href') == root for attrs in links)
    picker = next(attrs['href'] for attrs in links if urlsplit(attrs.get('href','')).path == '/library/pick')
    assert parse_qs(urlsplit(picker).query)['from'] == [root]
    pick_page = alice.get(picker)
    assert 'name="from"' in pick_page.text and 'data-library-url="/library?q=Portal&amp;status=Playing&amp;sort=rating"' in pick_page.text
    for origin in ('https://evil.example', '/players/alice_player', f'/library?list={foreign}'):
        page = alice.get('/library/lists',query_string={'from':origin})
        parser = LibraryParser();parser.feed(page.text)
        homes = [attrs['href'] for tag,attrs in parser.tags if tag == 'a' and urlsplit(attrs.get('href','')).path == '/library']
        assert homes and all(home == '/library' for home in homes)
