"""Public profile review and player search visibility, bounded queries, and fallbacks."""
from unittest.mock import Mock
from uuid import uuid4
import pytest
from app.catalog import CatalogError, IGDBClient
from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_game_reviews import public_author
from tests.test_public_catalog import fake_catalog, GAME


def add_review(app, owner=ALICE, catalog_id=123, body='PUBLIC REVIEW', **flags):
    with app.app_context():
        return get_db().execute('INSERT INTO public_game_reviews (owner_id,catalog_id,rating,body,has_spoilers,moderation_hidden) VALUES (?,?,9,?,?,?) RETURNING id', (owner,catalog_id,body,flags.get('spoilers',False),flags.get('hidden',False))).fetchone()[0]


@pytest.mark.parametrize('publish_from', ['add', 'edit'])
def test_library_only_reviews_stay_off_profiles_until_explicit_publication(accounts, publish_from):
    from tests.test_add_game_public_review import DATA, add
    from tests.test_edit_game_public_review import entry_path
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    assert add(alice, review='ONLY IN MY LIBRARY').status_code == 302
    anonymous = accounts.test_client()
    for client in (alice, anonymous):
        html = client.get('/players/alice_player').get_data(as_text=True)
        assert 'ONLY IN MY LIBRARY' not in html
        assert 'class="community-review profile-review-card"' not in html
    if publish_from == 'add':
        assert add(alice, platform='PS3', review='EXPLICITLY PUBLISHED', publish_review='yes').status_code == 303
    else:
        assert submit(alice, entry_path(accounts), {**DATA, 'review':'EXPLICITLY PUBLISHED', 'publish_review':'yes'}).status_code == 303
    assert b'EXPLICITLY PUBLISHED' in anonymous.get('/players/alice_player').data
    assert submit(alice, entry_path(accounts), {**DATA, 'review':'LATER PRIVATE CHANGES'}).status_code == 302
    for client in (alice, anonymous):
        html = client.get('/players/alice_player').get_data(as_text=True)
        assert 'EXPLICITLY PUBLISHED' in html and 'LATER PRIVATE CHANGES' not in html
    assert submit(alice, '/explore/games/123/reviews/delete', {}, source='/explore/games/123').status_code == 303
    assert b'EXPLICITLY PUBLISHED' not in anonymous.get('/players/alice_player').data


def test_public_and_owner_profiles_share_only_published_reviews(accounts):
    catalog=fake_catalog(accounts)
    alice=public_author(accounts,'alice')
    public_author(accounts,'bob')
    add_review(accounts)
    add_review(accounts,BOB,124,'BOB REVIEW')
    with accounts.app_context():
        get_db().execute("INSERT INTO games (owner_id,title,platform,review,rating) VALUES (?,'SECRET GAME','SECRET PLATFORM','SECRET NOTE',2)",(ALICE,))
    for client in [accounts.test_client(),alice]:
        response=client.get('/players/alice_player')
        html=response.get_data(as_text=True)
        assert response.status_code==200 and 'PUBLIC REVIEW' in html and 'Portal 2' in html and '4.5/5' in html
        assert 'BOB REVIEW' not in html and 'SECRET NOTE' not in html
        if client is not alice:
            for secret in ['SECRET GAME','SECRET PLATFORM',ALICE,'alice@example.test','alice-access','alice-refresh']:
                assert secret not in html
        assert response.headers['Cache-Control']=='private, no-store'
    assert catalog.get_game_cards.call_args.args[0]==[123]


def test_empty_visitor_profile_omits_sections_but_owner_keeps_setup_prompts(accounts):
    owner = public_author(accounts, 'alice')
    for client in (accounts.test_client(), sign_in(accounts, 'bob')):
        page = client.get('/players/alice_player')
        assert page.status_code == 200
        for marker in ('id="badges-title"', 'id="showcase-title"', 'id="playing-title"',
                       'id="completed-title"', 'id="public-reviews"', 'Public gaming statistics',
                       'No showcase shared.', 'No badges featured yet.', 'No public reviews to show yet.'):
            assert marker not in page.text
    own_page = owner.get('/players/alice_player')
    assert 'Build your showcase' in own_page.text or 'Add your first game' in own_page.text
    assert 'id="playing-title"' in own_page.text
    assert 'id="public-reviews"' in own_page.text


def test_privacy_moderation_unpublication_and_catalog_failure(accounts):
    catalog=fake_catalog(accounts)
    alice=public_author(accounts,'alice')
    add_review(accounts,body='VISIBLE PUBLISHED')
    add_review(accounts,catalog_id=124,body='HIDDEN MODERATION',hidden=True)
    catalog.get_game_cards.side_effect=CatalogError('Provider unavailable')
    page=accounts.test_client().get('/players/alice_player')
    assert page.status_code==200 and b'VISIBLE PUBLISHED' in page.data and b'Game #123' in page.data
    assert b'HIDDEN MODERATION' not in page.data
    submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'no'})
    assert accounts.test_client().get('/players/alice_player').status_code==404
    owner=alice.get('/players/alice_player').get_data(as_text=True)
    assert 'VISIBLE PUBLISHED' not in owner and 'hidden while your profile is private' in owner
    submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'yes'})
    with accounts.app_context():get_db().execute('DELETE FROM public_game_reviews WHERE owner_id=?',(ALICE,))
    assert b'VISIBLE PUBLISHED' not in accounts.test_client().get('/players/alice_player').data


def test_reported_reviews_are_hidden_for_reporter_on_profiles_too(accounts):
    fake_catalog(accounts)
    public_author(accounts,'alice');bob=public_author(accounts,'bob')
    review=add_review(accounts)
    with accounts.app_context():get_db().execute("INSERT INTO public_review_reports (review_id,reporter_id,reason) VALUES (?,?,'spam')",(review,BOB))
    assert b'PUBLIC REVIEW' in accounts.test_client().get('/players/alice_player').data
    assert b'PUBLIC REVIEW' not in bob.get('/players/alice_player').data


def test_spoilers_are_escaped_and_inside_a_closed_disclosure(accounts):
    fake_catalog(accounts);public_author(accounts,'alice')
    add_review(accounts,body='<script>spoiler()</script>',spoilers=True)
    html=accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert '<details class="profile-review-spoilers">' in html
    assert '&lt;script&gt;spoiler()&lt;/script&gt;' in html and '<script>spoiler()' not in html


@pytest.mark.parametrize('review_count', [11, 31])
def test_review_pagination_is_bounded_and_preserves_profile_route(accounts, review_count):
    catalog=fake_catalog(accounts);public_author(accounts,'alice')
    for n in range(review_count):add_review(accounts,catalog_id=200+n,body=f'REVIEW-{n:02d}')
    first=accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert first.count('class="community-review profile-review-card"')==10
    assert '/players/alice_player?reviews_page=2#public-reviews' in first
    assert len(catalog.get_game_cards.call_args.args[0])==10
    last_page = (review_count + 9) // 10
    for page_number in range(2, last_page + 1):
        html = accounts.test_client().get(f'/players/alice_player?reviews_page={page_number}').get_data(as_text=True)
        assert html.count('class="community-review profile-review-card"') == min(10, review_count - (page_number - 1) * 10)
        assert f'/players/alice_player?reviews_page={page_number - 1}#public-reviews' in html
        if page_number < last_page:
            assert f'/players/alice_player?reviews_page={page_number + 1}#public-reviews' in html
        else:
            assert 'REVIEW-00' in html and 'Older reviews' not in html
    for page in ['0','-1','10001','abc']:
        assert accounts.test_client().get('/players/alice_player?reviews_page='+page).status_code==400


def test_player_search_is_public_only_and_never_searches_email_or_aliases(accounts):
    alice=public_author(accounts,'alice');bob=sign_in(accounts,'bob')
    with accounts.app_context():
        get_db().execute("UPDATE profiles SET bio='SECRET BIO',share_bio=FALSE WHERE id=?",(ALICE,))
    anon=accounts.test_client()
    assert b'/players/alice_player' in anon.get('/community/players').data
    response=anon.get('/community/players?q=@ALICE')
    html=response.get_data(as_text=True)
    assert response.status_code==200 and '/players/alice_player' in html
    for secret in ['SECRET BIO',ALICE,BOB,'alice@example.test','alice-access','alice-refresh']:
        assert secret not in html
    assert b'alice_player' not in anon.get('/community/players?q=example.test').data
    assert b'class="player-result"' not in anon.get('/community/players?q=bob').data
    with accounts.app_context():
        get_db().execute("INSERT INTO profile_usernames (username,owner_id) VALUES ('former_alice',?)",(ALICE,))
    assert b'class="player-result"' not in anon.get('/community/players?q=former_alice').data
    assert b'alice_player' not in anon.get('/community/players?q=%25').data
    assert response.headers['Cache-Control']=='private, no-store'
    assert response.headers['X-Robots-Tag']=='noindex, nofollow'
    submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'no'})
    assert b'alice_player' not in anon.get('/community/players?q=alice').data


def test_search_validation_and_rate_limit(accounts):
    anon=accounts.test_client()
    for suffix in ['q=x','q='+('a'*81),'q=%00','q=@@','page=0','page=10001','page=abc']:
        assert anon.get('/community/players?'+suffix).status_code==400
    accounts.config['PUBLIC_PLAYER_REQUEST_LIMIT']=1
    assert anon.get('/community/players?q=Alice').status_code==200
    limited=anon.get('/community/players?q=Bob')
    assert limited.status_code==429 and limited.headers['Retry-After']=='60'


def test_search_pagination_and_html_escaping(accounts):
    with accounts.app_context():
        db=get_db()
        for n in range(22):
            owner=str(uuid4());username=f'player_{n:02d}'
            db.execute('INSERT INTO profiles (id,display_name) VALUES (?,?)',(owner,'<Player '+str(n)+'>'))
            db.execute('INSERT INTO profile_usernames (username,owner_id) VALUES (?,?)',(username,owner))
            db.execute('UPDATE profiles SET username=?,is_public=TRUE WHERE id=?',(username,owner))
    first=accounts.test_client().get('/community/players?q=Player').get_data(as_text=True)
    assert first.count('class="player-result"')==20 and 'page=2' in first and '&lt;Player' in first
    second=accounts.test_client().get('/community/players?q=Player&page=2').get_data(as_text=True)
    assert second.count('class="player-result"')==2


def test_directory_lists_newest_public_players_first_with_pagination(accounts):
    with accounts.app_context():
        db = get_db()
        for n in range(23):
            owner = str(uuid4())
            db.execute("INSERT INTO profiles (id,display_name,created_at) VALUES (?,?,?)",
                       (owner, f'New player {n:02d}', f'2026-01-{n+1:02d} 12:00:00'))
            db.execute('INSERT INTO profile_usernames (username,owner_id) VALUES (?,?)', (f'new_player_{n:02d}', owner))
            db.execute('UPDATE profiles SET username=?,is_public=TRUE WHERE id=?', (f'new_player_{n:02d}', owner))
        db.execute("UPDATE profiles SET is_public=FALSE WHERE username='new_player_22'")
    anonymous = accounts.test_client()
    first = anonymous.get('/community/players')
    assert first.status_code == 200
    assert first.text.count('class="player-result"') == 20
    assert first.text.index('/players/new_player_21') < first.text.index('/players/new_player_20')
    assert '/players/new_player_22' not in first.text
    assert '/players/new_player_00' not in first.text
    assert 'Newest players' in first.text and 'page=2' in first.text
    second = anonymous.get('/community/players?page=2')
    assert second.text.count('class="player-result"') == 2
    assert '/players/new_player_00' in second.text
    assert first.headers['Cache-Control'] == 'private, no-store'


@pytest.mark.parametrize('blocker,blocked', [(ALICE, BOB), (BOB, ALICE)])
def test_directory_respects_blocks_in_both_directions(accounts, blocker, blocked):
    alice = public_author(accounts, 'alice')
    public_author(accounts, 'bob')
    with accounts.app_context():
        get_db().execute('INSERT INTO player_blocks (blocker_id,blocked_id) VALUES (?,?)', (blocker, blocked))
    assert '/players/bob_player' not in alice.get('/community/players').text
    assert '/players/bob_player' in accounts.test_client().get('/community/players').text


def test_directory_uses_the_existing_public_lookup_rate_limit(accounts):
    accounts.config['PUBLIC_PLAYER_REQUEST_LIMIT'] = 1
    anonymous = accounts.test_client()
    assert anonymous.get('/community/players').status_code == 200
    limited = anonymous.get('/community/players')
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'


def test_public_metadata_is_batched_cached_and_bounded():
    client=IGDBClient('test','test')
    client._query_games=Mock(return_value=[GAME])
    assert client.get_game_cards([123,123,True,-1,'123'])=={123:GAME}
    assert 'where id = (123)' in client._query_games.call_args.args[0]
    assert client.get_game_cards([123])=={123:GAME} and client._query_games.call_count==1
    with pytest.raises(CatalogError):client.get_game_cards(range(1,52))
    client._card_cache={n:(999999999,{**GAME,'id':n}) for n in range(1,257)}
    client._query_games.return_value=[]
    assert client.get_game_cards([500])=={} and len(client._card_cache)==1
