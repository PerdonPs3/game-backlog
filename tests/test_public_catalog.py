"""Public browsing never exposes private entries or inserts games implicitly."""

from unittest.mock import Mock

import pytest

from app.catalog import CatalogError
from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


GAME = {'id':123, 'name':'Portal 2', 'cover':{'image_id':'co1rs4'},
        'first_release_date':1303171200, 'genres':[{'name':'Puzzle'}],
        'platforms':[{'name':'PC'}, {'name':'PS3'}], 'summary':'A story about testing and trust.'}


def fake_catalog(app):
    catalog=Mock()
    catalog.search_games.return_value=[GAME]
    catalog.get_game.side_effect=lambda game_id: GAME if game_id==123 else None
    app.extensions['igdb_client']=catalog
    return catalog


def test_media_gallery_has_safe_fallback_links_and_no_initial_video_player(accounts):
    catalog = fake_catalog(accounts)
    catalog.get_game.side_effect = None
    catalog.get_game.return_value = {**GAME, 'videos': [{'name': '<Trailer>', 'video_id': 'KOiuc9UWz1E'}],
                                   'screenshots': [{'image_id': 'shot_123'}]}
    page = accounts.test_client().get('/explore/games/123').get_data(as_text=True)
    assert 'data-media-gallery' in page and '&lt;Trailer&gt;' in page
    assert 'https://www.youtube.com/watch?v=KOiuc9UWz1E' in page
    assert 't_screenshot_huge/shot_123.jpg' in page
    assert '<iframe' not in page
    assert page.index('data-media-gallery') < page.index('About the game')
    catalog.get_game.return_value = GAME
    assert 'data-media-gallery' not in accounts.test_client().get('/explore/games/123').get_data(as_text=True)


def test_search_and_shareable_detail_work_without_login_and_without_writes(accounts):
    catalog=fake_catalog(accounts)
    alice=sign_in(accounts,'alice')
    with accounts.app_context():
        get_db().execute("INSERT INTO games (title, platform, review, owner_id, igdb_id) VALUES ('PRIVATE TITLE', 'PC', 'PRIVATE REVIEW', ?, 123)", (ALICE,))
    anon=accounts.test_client()
    assert anon.get('/explore').status_code==200
    catalog.search_games.assert_not_called()
    search=anon.get('/explore?q=Portal').get_data(as_text=True)
    assert 'Portal 2' in search and 'href="/explore/games/123"' in search
    response=anon.get('/explore/games/123')
    page=response.get_data(as_text=True)
    assert response.status_code==200 and 'Puzzle' in page and '2011-04-19' in page
    assert GAME['summary'] in page and 'PS3' in page and '/explore/games/123/add' in page
    for secret in ('PRIVATE TITLE','PRIVATE REVIEW',ALICE,'alice@example.test','alice-access','alice-refresh'):
        assert secret not in page
    assert response.headers['Cache-Control']=='private, no-store'
    assert response.headers['Referrer-Policy']=='same-origin'
    assert anon.get('/games/1').location.endswith('/account/login')
    assert anon.get('/catalog/games/123').status_code==401
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0]==1
    own=alice.get('/library').get_data(as_text=True)
    assert 'href="/explore/games/123"' in own and '>My entry</a>' in own
    assert 'data-game-details' in own


def test_selection_survives_login_but_requires_explicit_add_and_revalidates_duplicate(accounts):
    fake_catalog(accounts)
    with accounts.app_context():
        get_db().execute("INSERT INTO profiles (id,display_name) VALUES (?, 'Alice')", (ALICE,))
    client=accounts.test_client()
    assert client.get('/explore/games/123/add').location.endswith('/account/login')
    login=submit(client,'/account/login',{'email':'alice@example.test','password':'test-password'})
    assert login.location.endswith('/games/new?igdb_id=123')
    form=client.get(login.location).get_data(as_text=True)
    assert 'value="Portal 2"' in form and 'value="123"' in form and 'value="PS3"' in form
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0]==0
    data={'title':'Portal 2','platform':'PC','status':'Backlog','igdb_id':'123'}
    assert submit(client,'/games/new',data,source=login.location).status_code==302
    assert 'already in your collection' in submit(client,'/games/new',data,source=login.location).get_data(as_text=True)
    with accounts.app_context():
        rows=get_db().execute('SELECT owner_id FROM games').fetchall()
        assert len(rows)==1 and str(rows[0][0])==ALICE
    with client.session_transaction() as cookie:
        assert 'catalog_selection' not in cookie


def test_selection_survives_registration_confirmation_and_profile_setup(accounts):
    fake_catalog(accounts)
    client=accounts.test_client()
    client.get('/explore/games/123/add')
    registered=submit(client,'/account/register',{'email':'alice@example.test','password':'test-password','confirmation':'test-password'})
    assert 'Check your email' in registered.get_data(as_text=True)
    logged_in=submit(client,'/account/login',{'email':'alice@example.test','password':'test-password'})
    assert logged_in.location.endswith('/account/profile/edit')
    setup=submit(client,'/account/profile/edit',{'display_name':'Alice','username':'alice_player'})
    assert setup.status_code==303 and setup.location.endswith('/profile/alice_player#profile-feedback')
    overview = client.get(setup.location).get_data(as_text=True)
    assert 'Your profile is ready.' in overview and 'Continue to your selected game' in overview
    continuation = client.get('/explore/games/123/add')
    assert continuation.location.endswith('/games/new?igdb_id=123')
    assert 'value="Portal 2"' in client.get(continuation.location).get_data(as_text=True)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0]==0


def test_recovery_keeps_the_selection_but_cannot_open_add_form_until_normal_login(accounts):
    fake_catalog(accounts)
    client=sign_in(accounts,'alice')
    submit(client,'/account/logout',{},source='/account/profile/edit')
    submit(client,'/account/verify-recovery',{'email':'alice@example.test','code':'123456'})
    assert client.get('/explore/games/123/add').location.endswith('/account/password')
    assert client.get('/games/new?igdb_id=123').location.endswith('/account/password')
    result=submit(client,'/account/password',{'password':'new-password','confirmation':'new-password'})
    assert result.location.endswith('/account/login')
    login=submit(client,'/account/login',{'email':'alice@example.test','password':'new-password'})
    assert login.location.endswith('/games/new?igdb_id=123')


@pytest.mark.parametrize('value',[{'id':'https://evil.invalid','at':1800000000}, {'id':123,'at':1800000000-1801}, {'id':123,'at':1800000001}, {'id':True,'at':1800000000}])
def test_invalid_expired_or_external_destinations_never_redirect(accounts,monkeypatch,value):
    monkeypatch.setattr('app.catalog_journey.time',lambda:1800000000)
    with accounts.app_context():
        get_db().execute("INSERT INTO profiles (id,display_name) VALUES (?, 'Alice')", (ALICE,))
    client=accounts.test_client()
    with client.session_transaction() as cookie:
        cookie['catalog_selection']=value
    result=submit(client,'/account/login?next=https://evil.invalid',{'email':'alice@example.test','password':'test-password'})
    assert result.location.endswith('/library')


def test_public_input_bounds_safe_metadata_and_errors(client,app):
    catalog=fake_catalog(app)
    assert client.get('/explore?q=x').status_code==200
    assert client.get('/explore',query_string={'q':'x'*201}).status_code==400
    catalog.search_games.assert_not_called()
    for path in ('/explore/games/0','/explore/games/'+str(2**63),'/explore/games/0/add'):
        assert client.get(path).status_code==404
    catalog.get_game.assert_not_called()
    assert client.get('/explore/games/999').status_code==404
    catalog.get_game.side_effect=None
    catalog.get_game.return_value={**GAME,'name':'<script>bad()</script>','summary':'<img src=x onerror=bad()>','cover':{'image_id':'javascript:bad'}}
    page=client.get('/explore/games/123').get_data(as_text=True)
    assert '&lt;script&gt;' in page and '&lt;img' in page
    assert '<script>bad()' not in page and '<img src=x' not in page and 'javascript:bad' not in page
    catalog.get_game.side_effect=CatalogError('PRIVATE CLIENT SECRET')
    failure=client.get('/explore/games/123')
    assert failure.status_code==503 and b'PRIVATE CLIENT SECRET' not in failure.data
    catalog.search_games.side_effect=CatalogError('PRIVATE CLIENT SECRET')
    assert client.get('/explore?q=Portal').status_code==503


def test_public_budget_limits_provider_calls_and_sends_retry_after(client,app,monkeypatch):
    now=[100]
    monkeypatch.setattr('app.public_catalog.monotonic',lambda:now[0])
    catalog=fake_catalog(app)
    app.config['PUBLIC_CATALOG_REQUEST_LIMIT']=2
    assert client.get('/explore?q=Portal').status_code==200
    assert client.get('/explore/games/123').status_code==200
    limited=client.get('/explore?q=Another')
    assert limited.status_code==429 and limited.headers['Retry-After']=='60'
    assert catalog.search_games.call_count==1 and catalog.get_game.call_count==1
    now[0]=160
    assert client.get('/explore?q=Another').status_code==200


def test_catalog_prefill_is_read_only_and_post_cannot_trust_metadata(client,app,stored_games):
    fake_catalog(app)
    assert client.get('/explore/games/123/add').location.endswith('/games/new?igdb_id=123')
    assert client.get('/games/new?igdb_id=123').status_code==200
    assert stored_games()==[]
    for raw in ('x','0',str(2**63),'1;DROP TABLE games'):
        assert client.get('/games/new',query_string={'igdb_id':raw}).status_code==400
    assert client.get('/games/new?igdb_id=999').status_code==404
    bad=submit(client,'/games/new',{'igdb_id':'123','title':'Forged title','platform':'PC','status':'Backlog'})
    assert 'choose a game from the catalog' in bad.get_data(as_text=True)
    assert stored_games()==[]


def test_public_showcase_links_use_catalog_identity_not_private_entry_id(accounts):
    fake_catalog(accounts)
    alice=sign_in(accounts,'alice')
    with accounts.app_context():
        db=get_db()
        game_id=db.execute("INSERT INTO games (title,platform,igdb_id,owner_id) VALUES ('Portal 2','PC',123,?) RETURNING id",(ALICE,)).fetchone()[0]
        db.execute('INSERT INTO profile_showcase VALUES (?,1,?)',(ALICE,game_id))
    submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'yes','share_showcase':'yes'})
    page=accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert 'href="/explore/games/123"' in page and f'href="/games/{game_id}"' not in page and ALICE not in page


def test_public_suggestions_are_bounded_and_share_the_provider_budget(app):
    catalog = fake_catalog(app)
    client = app.test_client()
    for query in ('', 'g', 'x' * 201):
        response = client.get('/explore/suggestions', query_string={'q': query})
        assert response.status_code == (400 if len(query) > 200 else 200)
    catalog.search_games.assert_not_called()
    catalog.search_games.return_value = [{**GAME, 'id': number} for number in range(1, 15)]
    app.config['PUBLIC_CATALOG_REQUEST_LIMIT'] = 2
    response = client.get('/explore/suggestions?q=god')
    assert response.status_code == 200
    assert len(response.json['games']) == 10
    assert 'summary' not in response.json['games'][0]
    assert response.json['games'][0]['name'] == 'Portal 2'
    assert response.headers['Cache-Control'] == 'private, no-store'
    catalog.search_games.side_effect = CatalogError('private provider credentials')
    failed = client.get('/explore/suggestions?q=gods')
    assert failed.status_code == 503
    assert 'private provider' not in failed.get_data(as_text=True)
    limited = client.get('/explore/suggestions?q=god')
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'
    assert catalog.search_games.call_count == 2
    assert 'data-browse-url="/explore/games/0"' in client.get('/explore').get_data(as_text=True)


def test_filtered_search_paginates_and_preserves_the_filter(app):
    catalog = fake_catalog(app)
    catalog.search_games.return_value = [{**GAME, 'id': n, 'name': f'Match {n:03d}'} for n in range(1, 66)]
    client = app.test_client()
    first = client.get('/explore?q=zelda&content=all').get_data(as_text=True)
    assert 'Match 001' in first and 'Match 030' in first and 'Match 031' not in first
    assert 'content=all' in first and 'page=2' in first
    second = client.get('/explore?q=zelda&content=all&page=2').get_data(as_text=True)
    assert 'Match 031' in second and 'Match 060' in second and 'Match 001' not in second
    catalog.search_games.assert_called_with('zelda', include_community=True)
    client.get('/explore/suggestions?q=zelda&content=official')
    catalog.search_games.assert_called_with('zelda', include_community=False)


@pytest.mark.parametrize('url', ['/explore?q=zelda&content=invalid', '/explore?q=zelda&page=-1', '/explore?q=zelda&page=oops', '/explore?q=zelda&page=999', '/explore/suggestions?q=zelda&content=invalid', '/catalog/search?q=zelda&content=invalid'])
def test_invalid_catalog_filters_never_reach_provider(client, app, url):
    catalog = fake_catalog(app)
    assert client.get(url).status_code == 400
    catalog.search_games.assert_not_called()
