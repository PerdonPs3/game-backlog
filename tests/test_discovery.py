"""Explainable rankings and account isolation on disposable databases."""

from unittest.mock import Mock

import pytest

from app.catalog import CatalogError, IGDBClient, discovery_traits
from app.db import get_db
from app.discovery import affinities, preference_sources, rank_candidates
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


def game(catalog_id, genre='Puzzle', platform=6):
    return {'id': catalog_id, 'name': f'Adventure {catalog_id}',
            'genres': [{'name': genre}], 'platforms': [{'id': platform, 'name': 'PC'}],
            'cover': {'image_id': 'co1rs4'}, 'total_rating_count': 20}


def provider(app):
    client = Mock()
    client.get_discovery_games.return_value = [game(20), game(30, 'Shooter')]
    client.get_game_traits.return_value = {value: discovery_traits(game(value, genre)) for value, genre in ((10, 'Puzzle'), (11, 'Shooter'), (12, 'Adventure'))}
    client.get_game.side_effect = lambda value: game(value)
    app.extensions['igdb_client'] = client
    return client


def add_rating(app, owner, catalog_id=10, title='Private favorite', rating=10):
    with app.app_context():
        get_db().execute('INSERT INTO games (owner_id, igdb_id, title, platform, rating) VALUES (?, ?, ?, ?, ?)',
                         (owner, catalog_id, title, 'PC', rating))


def test_rating_signals_deduplicate_copies_and_outweigh_wishes():
    library = [{'id': 1, 'igdb_id': 10, 'rating': 10, 'title': 'Old'},
               {'id': 2, 'igdb_id': 10, 'rating': 2, 'title': 'New'},
               {'id': 3, 'igdb_id': 11, 'rating': 6, 'title': 'Neutral'}]
    wishes = [{'catalog_id': value, 'title': 'Wish'} for value in (10, 11, 12)]
    sources = preference_sources(library, wishes)
    assert [(row['igdb_id'], row['kind']) for row in sources] == [(10, 'rating'), (12, 'wishlist')]
    weights = affinities(sources, {10: ('Puzzle',), 12: ('Adventure',)})
    assert weights['Puzzle'] < 0 < weights['Adventure'] < 1


def test_rankings_explain_actual_matches_and_negative_signals_reduce_them():
    sources = preference_sources([
        {'id': 1, 'igdb_id': 10, 'rating': 10, 'title': '<Favorite>'},
        {'id': 2, 'igdb_id': 11, 'rating': 2, 'title': 'Disliked'}], [])
    candidates = [game(20), game(30, 'Shooter')]
    ranked = rank_candidates(candidates, sources, {10: ('Puzzle',), 11: ('Shooter',)})
    assert len(ranked) == 1 and ranked[0][0]['id'] == 20
    assert ranked[0][1]['title'] == '<Favorite>' and ranked[0][1]['genres'] == ['Puzzle']
    assert rank_candidates(candidates, sources, {}) == []


def test_specific_genre_matches_rank_above_a_single_broad_overlap():
    sources = preference_sources([{'id': 1, 'igdb_id': 10, 'rating': 10, 'title': 'Favorite'}], [])
    specific = game(20)
    specific['genres'] = [{'name': 'Puzzle'}, {'name': 'Adventure'}]
    broad = game(30, 'Adventure')
    ranked = rank_candidates([broad, specific], sources, {10: ('Puzzle', 'Adventure')})
    assert [row['id'] for row, _ in ranked] == [20]


def described_game(catalog_id, title, genres, themes, perspective, modes=('Single player',)):
    return {**game(catalog_id), 'name': title,
            'genres': [{'name': name} for name in genres],
            'themes': [{'name': name} for name in themes],
            'player_perspectives': [{'name': perspective}] if perspective else [],
            'game_modes': [{'name': name} for name in modes]}


def test_hollow_knight_never_explains_outlast_and_ori_uses_the_correct_reference():
    # Public provider metadata captured during the owner's reported regression.
    hollow = described_game(14593, 'Hollow Knight', ('Platform', 'Adventure', 'Indie'), ('Action', 'Fantasy'), 'Side view')
    portal = described_game(72, 'Portal 2', ('Platform', 'Puzzle', 'Adventure'), ('Action', 'Science fiction', 'Comedy'), 'First person')
    outlast = described_game(1910, 'Outlast', ('Adventure', 'Indie'), ('Action', 'Horror', 'Survival', 'Stealth', 'Mystery'), 'First person')
    ori = described_game(7344, 'Ori and the Blind Forest', ('Platform', 'Puzzle', 'Adventure'), ('Action', 'Fantasy', 'Thriller'), 'Side view')
    celeste = described_game(26226, 'Celeste', ('Platform', 'Adventure', 'Indie'), ('Action', 'Fantasy'), 'Side view')
    hollow['keywords'] = [{'name': 'metroidvania'}]
    ori['keywords'] = [{'name': 'metroidvania'}, {'name': 'puzzle platformer'}]
    sources = preference_sources([{'id': index, 'igdb_id': raw['id'], 'title': raw['name'], 'rating': 10}
                                  for index, raw in enumerate((hollow, portal), start=1)], [])
    traits = {raw['id']: discovery_traits(raw) for raw in (hollow, portal)}
    genres = {key: value['genres'] for key, value in traits.items()}
    ranked = rank_candidates([outlast, ori, celeste], sources, genres, traits)
    reasons = {raw['name']: reason for raw, reason in ranked}
    assert 'Outlast' not in reasons
    assert reasons['Ori and the Blind Forest']['title'] == 'Hollow Knight'
    assert ranked[0][0]['name'] == 'Ori and the Blind Forest'
    assert 'Metroidvania' in reasons['Ori and the Blind Forest']['matches']
    assert reasons['Celeste']['title'] == 'Hollow Knight'
    assert 'Platform' in reasons['Celeste']['matches'] and 'Side view' in reasons['Celeste']['matches']
    # Broad labels remain insufficient even if perspective/theme data is missing.
    assert rank_candidates([game(1910, 'Adventure')], sources, genres) == []


def test_horror_can_match_horror_but_known_modes_and_perspectives_must_agree():
    source = described_game(1, 'Liked horror', ('Adventure','Indie'), ('Horror','Survival'), 'First person')
    candidate = described_game(2, 'Another horror', ('Adventure','Indie'), ('Horror','Survival'), 'First person')
    sources = preference_sources([{'id': 1, 'igdb_id': 1, 'title': source['name'], 'rating': 10}], [])
    traits = {1: discovery_traits(source)}
    genre_map = {1: traits[1]['genres']}
    ranked = rank_candidates([candidate], sources, genre_map, traits)
    assert len(ranked) == 1 and 'Horror' in ranked[0][1]['matches']
    incompatible_mode = {**candidate, 'game_modes': [{'name':'Multiplayer'}]}
    incompatible_view = {**candidate, 'player_perspectives': [{'name':'Side view'}]}
    assert rank_candidates([incompatible_mode, incompatible_view], sources, genre_map, traits) == []


def test_gameplay_overlap_does_not_turn_a_non_horror_favorite_into_horror_evidence():
    source = described_game(1, 'Liked platformer', ('Platform',), ('Action','Fantasy'), 'Side view')
    candidate = described_game(2, 'Horror platformer', ('Platform',), ('Action','Horror'), 'Side view')
    sources = preference_sources([{'id': 1,'igdb_id': 1,'title': source['name'],'rating': 10}], [])
    assert rank_candidates([candidate], sources, {1: ('Platform',)}, {1: discovery_traits(source)}) == []


def test_trait_metadata_is_bounded_cached_and_missing_data_stays_unknown(monkeypatch):
    provider = IGDBClient('fake','fake')
    query = Mock(return_value=[described_game(1,'Public game',('Platform',),('Fantasy',),'Side view')])
    monkeypatch.setattr(provider, '_query_games', query)
    traits = provider.get_game_traits([1,2])
    assert traits[1]['player_perspectives'] == ('Side view',)
    assert traits[2] == discovery_traits({})
    assert provider.get_game_traits([1,2]) == traits and query.call_count == 1
    assert 'player_perspectives.name' in query.call_args.args[0]
    with pytest.raises(CatalogError):
        provider.get_game_traits(range(1,92))


def test_a_wishlist_game_cannot_explain_its_own_recommendation():
    sources = preference_sources([], [{'catalog_id': 20,'title':'Desired puzzle'}])
    assert rank_candidates([game(20)], sources, {20: ('Puzzle',)}) == []
    assert rank_candidates([game(30)], sources, {20: ('Puzzle',)})[0][1]['title'] == 'Desired puzzle'


def test_only_explicit_gameplay_keywords_are_normalized_into_mechanics():
    raw = {'keywords': [{'name': 'souls-like'}, {'name': 'Soulslike'},
                        {'name': 'Metroidvania'}, {'name': 'indie'}, {'name': 'fantasy'}, None]}
    assert discovery_traits(raw)['mechanics'] == ('Metroidvania', 'Soulslike')
    assert discovery_traits({'keywords': 'metroidvania'})['mechanics'] == ()


@pytest.mark.parametrize('state,destination', [('recovery','/account/password'), ('unfinished','/settings/profile')])
def test_recovery_and_unfinished_sessions_cannot_request_recommendations(accounts, state, destination):
    catalog = provider(accounts)
    alice = sign_in(accounts, 'alice')
    with accounts.app_context():
        if state == 'recovery':
            get_db().execute('UPDATE account_sessions SET recovery = 1')
        else:
            get_db().execute("UPDATE profiles SET display_name = '' WHERE id = ?", (ALICE,))
    response = alice.get('/discover')
    assert response.status_code == 302 and destination in response.location
    catalog.get_discovery_games.assert_not_called()


def test_owner_recommendations_exclude_owned_games_escape_evidence_and_never_write(accounts):
    client = provider(accounts)
    alice = sign_in(accounts, 'alice')
    add_rating(accounts, ALICE, title='<Favorite puzzle>')
    client.get_discovery_games.return_value = [game(10), game(20), game(30, 'Shooter')]
    response = alice.get('/discover')
    page = response.get_data(as_text=True)
    assert response.status_code == 200 and 'Picked for your taste' in page
    assert 'Adventure 20' in page and 'Adventure 10' not in page and 'Adventure 30' not in page
    assert '&lt;Favorite puzzle&gt;' in page and '<Favorite puzzle>' not in page and '5/5' in page
    assert 'private, no-store' == response.headers['Cache-Control']
    assert response.headers['Referrer-Policy'] == 'same-origin'
    client.get_discovery_games.assert_called_once_with(('Puzzle',), None)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 1
        assert get_db().execute('SELECT COUNT(*) FROM wishlist_games').fetchone()[0] == 0


def test_private_signals_and_saved_wishes_never_cross_accounts_or_anonymous_requests(accounts):
    client = provider(accounts)
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    add_rating(accounts, ALICE, 10, 'ALICE PRIVATE FAVORITE')
    add_rating(accounts, BOB, 11, 'BOB PRIVATE FAVORITE')
    with accounts.app_context():
        get_db().execute("INSERT INTO wishlist_games (owner_id,catalog_id,title) VALUES (?,20,'ALICE SECRET WISH')", (ALICE,))
    alice_page = alice.get('/discover').get_data(as_text=True)
    assert 'BOB PRIVATE FAVORITE' not in alice_page and 'On your wishlist' in alice_page
    assert set(client.get_game_traits.call_args.args[0]) == {10, 20}
    client.reset_mock()
    bob_page = bob.get('/discover').get_data(as_text=True)
    assert 'ALICE PRIVATE FAVORITE' not in bob_page and 'ALICE SECRET WISH' not in bob_page
    assert 'On your wishlist' not in bob_page
    assert client.get_game_traits.call_args.args[0] == [11]
    client.reset_mock()
    anon = accounts.test_client().get('/discover')
    assert anon.status_code == 200 and b'Popular picks' in anon.data
    assert b'PRIVATE FAVORITE' not in anon.data and b'SECRET WISH' not in anon.data
    client.get_game_traits.assert_not_called()


def test_wishlist_signals_are_weak_but_explained(accounts):
    client = provider(accounts)
    alice = sign_in(accounts, 'alice')
    with accounts.app_context():
        get_db().execute("INSERT INTO wishlist_games (owner_id,catalog_id,title) VALUES (?,10,'Desired puzzle')", (ALICE,))
    page = alice.get('/discover').get_data(as_text=True)
    assert 'Inspired by <strong>Desired puzzle</strong> on your wishlist.' in page
    assert 'Adventure 20' in page and 'Adventure 30' not in page


def test_popular_mode_does_not_fetch_preferences_and_filters_intersect(accounts):
    client = provider(accounts)
    alice = sign_in(accounts, 'alice')
    add_rating(accounts, ALICE)
    client.get_discovery_games.return_value = [game(20), game(30, 'Shooter'), game(40, 'Puzzle', 9)]
    page = alice.get('/discover?mode=popular&genre=Puzzle&platform=6').get_data(as_text=True)
    assert 'Adventure 20' in page and 'Adventure 30' not in page and 'Adventure 40' not in page
    client.get_game_traits.assert_not_called()
    client.get_discovery_games.assert_called_once_with(('Puzzle',), 6)


@pytest.mark.parametrize('query', ['genre=made-up', 'platform=999', 'platform=evil', 'mode=secret', 'page=0', 'page=18', 'page=no'])
def test_invalid_filters_rejected_before_upstream_calls(app, client, query):
    catalog = provider(app)
    assert client.get('/discover?' + query).status_code == 400
    catalog.get_discovery_games.assert_not_called()


def test_pagination_preserves_filters_and_outages_are_explicit(app, client):
    catalog = provider(app)
    catalog.get_discovery_games.return_value = [game(i) for i in range(100, 125)]
    page = client.get('/discover?genre=Puzzle&platform=6&page=2').get_data(as_text=True)
    assert 'Adventure 112' in page and 'Adventure 100' not in page
    assert 'page=3' in page and 'platform=6' in page and 'genre=Puzzle' in page
    assert client.get('/discover?page=4').status_code == 404
    catalog.get_discovery_games.side_effect = CatalogError('private upstream body')
    error = client.get('/discover')
    assert error.status_code == 503 and b'temporarily unavailable' in error.data
    assert b'private upstream body' not in error.data
    app.config['PUBLIC_CATALOG_REQUEST_LIMIT'] = 0
    response = client.get('/discover')
    assert response.status_code == 429 and response.headers['Retry-After'] == '60'


def test_save_from_card_requires_csrf_revalidates_and_returns_to_filtered_discover(accounts):
    catalog = provider(accounts)
    alice = sign_in(accounts, 'alice')
    assert alice.post('/wishlist/games/20/add', data={'return_to': 'discover'}).status_code == 400
    result = submit(alice, '/wishlist/games/20/add',
                    {'return_to': 'discover', 'genre': 'Puzzle', 'platform': '6', 'mode': 'popular'}, source='/discover')
    assert result.status_code == 303 and '/discover?' in result.location and 'genre=Puzzle' in result.location
    assert b'On your wishlist' in alice.get(result.location).data
    catalog.get_game.assert_called_with(20)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM wishlist_games WHERE owner_id = ?', (ALICE,)).fetchone()[0] == 1
        assert get_db().execute('SELECT COUNT(*) FROM wishlist_games WHERE owner_id = ?', (BOB,)).fetchone()[0] == 0
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0


def test_catalog_candidates_are_bounded_cached_and_filter_only_public_fields(monkeypatch):
    client = IGDBClient('fake', 'fake')
    query = Mock(return_value=[game(20), game(20), {**game(30), 'game_type': {'type': 'Mod'}}])
    monkeypatch.setattr(client, '_query_games', query)
    assert [row['id'] for row in client.get_discovery_games(('Puzzle',), 6)] == [20]
    client.get_discovery_games(('Puzzle',), 6)
    assert query.call_count == 1
    text = query.call_args.args[0]
    assert 'genres.name = ("Puzzle")' in text and 'platforms = (6)' in text and 'limit 200' in text
    assert 'rating' not in text.replace('total_rating_count', '')
    assert 'owner' not in text and 'review' not in text
    with pytest.raises(CatalogError):
        client.get_discovery_games(platform='6; drop')
