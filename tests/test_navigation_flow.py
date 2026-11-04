"""Canonical navigation, safe returns and public/private game boundaries."""

from urllib.parse import parse_qs, urlsplit
from html import unescape
import re

import pytest

from app.catalog import CatalogError
from app.db import get_db
from app.navigation import game_url, safe_destination
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_public_catalog import fake_catalog


def seed(app, owner, platform='PC', catalog_id=123, notes='PRIVATE NOTES'):
    with app.app_context():
        return get_db().execute("INSERT INTO games (owner_id,igdb_id,title,platform,status,rating,review) VALUES (?,?,'Portal 2',?,'Playing',9,?) RETURNING id", (owner,catalog_id,platform,notes)).fetchone()[0]


def test_showcase_game_return_keeps_profile_section_for_owner_and_visitor(accounts):
    fake_catalog(accounts)
    owner = sign_in(accounts, 'alice')
    assert submit(owner, '/account/profile/sharing', {'username': 'alice_player', 'is_public': 'yes', 'share_showcase': 'yes'}).status_code == 303
    game_id = seed(accounts, ALICE)
    with accounts.app_context():
        get_db().execute('INSERT INTO profile_showcase (owner_id,position,game_id) VALUES (?,1,?)', (ALICE,game_id))
    for client in (owner, accounts.test_client()):
        profile = client.get('/players/alice_player').get_data(as_text=True)
        match = re.search(r'class="profile-featured-game" href="([^"]+)"', profile)
        assert match
        game_path = unescape(match.group(1))
        assert parse_qs(urlsplit(game_path).query)['from'] == ['/players/alice_player#showcase-title']
        game = client.get(game_path)
        assert game.status_code == 200
        assert 'href="/players/alice_player#showcase-title"' in game.get_data(as_text=True)
        assert 'Back to profile' in game.get_data(as_text=True)


def test_library_and_profiles_have_stable_owner_scoped_addresses(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts,'alice')
    seed(accounts,ALICE)
    page = alice.get('/library')
    assert page.status_code == 200
    assert '<span>Library</span>' in page.text and '<span>Community</span>' in page.text
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


def account_menu_avatar(html):
    import re
    return re.search(r'<span class="account-menu-avatar"[^>]*>(.*?)</span>', html, re.S)[1]


def test_account_avatar_uses_the_signed_in_private_photo_on_other_profiles(accounts):
    from tests.test_game_reviews import public_author
    alice = public_author(accounts, 'alice')
    bob = public_author(accounts, 'bob')
    with accounts.app_context():
        db = get_db()
        db.execute('UPDATE profiles SET avatar_image = ?, share_photo = FALSE WHERE id = ?', (b'ALICE PRIVATE PHOTO', ALICE))
        db.execute('UPDATE profiles SET avatar_image = ?, share_photo = TRUE WHERE id = ?', (b'BOB PUBLIC PHOTO', BOB))
    page = alice.get('/players/bob_player')
    assert page.status_code == 200
    avatar = account_menu_avatar(page.text)
    assert 'src="/account/profile/photo"' in avatar
    assert '/players/bob_player/photo' not in avatar
    assert alice.get('/account/profile/photo').data == b'ALICE PRIVATE PHOTO'
    assert bob.get('/account/profile/photo').data == b'BOB PUBLIC PHOTO'
    assert accounts.test_client().get('/account/profile/photo').status_code == 401
    assert page.headers['Cache-Control'] == 'private, no-store'
    # The private photo stays owner-only even though it is visible in their menu.
    assert accounts.test_client().get('/players/alice_player/photo').status_code == 404


def test_account_avatar_falls_back_to_initial_without_a_photo(accounts):
    alice = sign_in(accounts, 'alice')
    page = alice.get('/settings/profile')
    assert 'aria-label="Settings sections"' not in page.text
    assert page.text.count('href="/settings/data"') == 1
    assert page.status_code == 200
    assert account_menu_avatar(page.text).strip() == 'A'
    assert '<img' not in account_menu_avatar(page.text)


def test_profiles_and_add_game_omit_redundant_return_bar(accounts):
    from tests.test_game_reviews import public_author
    alice = public_author(accounts, 'alice')
    public_author(accounts, 'bob')
    for client, path in [(alice, '/players/alice_player'), (alice, '/players/bob_player'),
                         (accounts.test_client(), '/players/bob_player')]:
        page = client.get(path)
        assert page.status_code == 200
        assert 'class="workspace-return"' not in page.text
    page = alice.get('/library/add')
    assert page.status_code == 200
    assert 'class="workspace-return"' not in page.text
    page = alice.get('/settings/profile/showcase')
    assert page.status_code == 200
    assert 'class="workspace-return"' in page.text


class FlowElements:
    def __init__(self, html):
        from html.parser import HTMLParser
        self.elements = []
        target = self.elements
        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                target.append((tag, dict(attrs)))
        Parser().feed(html)

    def matching(self, tag, **attrs):
        return [item for kind, item in self.elements if kind == tag and all(item.get(key) == value for key, value in attrs.items())]


def test_catalog_lookup_pages_offer_one_search_without_losing_autocomplete(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    for client in (alice, accounts.test_client()):
        page = client.get('/discover/browse?q=Portal&content=all')
        assert page.status_code == 200
        parsed = FlowElements(page.text)
        assert len(parsed.matching('input', id='catalog-query', role='combobox')) == 1
        assert len(parsed.matching('form', role='search')) == 1
        assert 'selected' in parsed.matching('option', value='all')[0]
        assert 'Discover your<br>' not in page.text
        assert 'Search <em>games.</em>' in page.text
        assert '/games/123/portal-2?' in page.text
    create = alice.get('/library/add')
    assert create.status_code == 200
    parsed = FlowElements(create.text)
    assert len(parsed.matching('input', id='title', role='combobox')) == 1
    assert not parsed.matching('form', role='search')
    assert not parsed.matching('nav', **{'aria-label': 'Library sections'})
    assert 'data-details-url=' in create.text
    assert 'class="visually-hidden">Private notes</label>' in create.text


def test_library_and_wishlist_search_scopes_are_distinct_from_catalog(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    seed(accounts, ALICE)
    page = alice.get('/library')
    parsed = FlowElements(page.text)
    assert len(parsed.matching('input', **{'aria-label': 'Search all games'})) == 1
    assert len(parsed.matching('input', id='title-search', placeholder='Search your library…')) == 1
    assert parsed.matching('form', **{'aria-label': 'Search the game catalog'})[0]['action'] == '/discover/browse'
    assert parsed.matching('input', id='title-search')[0]['name'] == 'q'


def test_connections_has_one_contextual_find_players_action(accounts):
    from tests.test_game_reviews import public_author
    alice = public_author(accounts, 'alice')
    page = alice.get('/community/connections')
    assert page.status_code == 200
    parsed = FlowElements(page.text)
    links = parsed.matching('a', href='/community/players')
    # Main Community entry, section tab, and one contextual action.
    assert len(links) == 3
    assert len([link for link in links if link.get('class') == 'connection-discover']) == 1
    assert 'Follow by username' in page.text
    assert 'Privacy settings' in page.text


def test_search_to_add_and_edit_retains_the_game_and_return_context(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    origin = '/discover/browse?q=Portal&content=all'
    game_page = alice.get('/games/123/portal-2', query_string={'from': origin})
    assert game_page.status_code == 200
    parsed = FlowElements(game_page.text)
    more = next(item['href'] for tag, item in parsed.elements if tag == 'a' and item.get('class') == 'catalog-more-options')
    add = alice.get(more, follow_redirects=True)
    assert add.status_code == 200
    fields = FlowElements(add.text)
    assert fields.matching('input', id='igdb-id')[0]['value'] == '123'
    return_to_game = fields.matching('input', name='return_path')[0]['value']
    assert urlsplit(return_to_game).path == '/games/123/portal-2'
    assert parse_qs(urlsplit(return_to_game).query)['from'] == [origin]
    result = submit(alice, '/library/add', {'igdb_id': '123', 'title': 'Portal 2', 'platform': 'PC', 'status': 'Playing', 'return_path': return_to_game})
    assert result.status_code == 302 and result.location == return_to_game
    with accounts.app_context():
        entry = get_db().execute('SELECT id FROM games WHERE owner_id = ? AND igdb_id = ?', (ALICE, 123)).fetchone()['id']
    destination = '/library?q=Portal&status=Playing&sort=title'
    edit = alice.get(f'/library/entries/{entry}/edit', query_string={'from': destination})
    assert FlowElements(edit.text).matching('input', name='return_path')[0]['value'] == destination
    assert not FlowElements(edit.text).matching('nav', **{'aria-label': 'Library sections'})
