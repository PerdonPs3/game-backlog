"""Explainable rankings and account isolation on disposable databases."""

from unittest.mock import Mock

import pytest

from app.catalog import CatalogError, IGDBClient
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
    client.get_game_genres.return_value = {10: ('Puzzle',), 11: ('Shooter',), 12: ('Adventure',)}
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
    assert [row['id'] for row, _ in ranked] == [20, 30]


@pytest.mark.parametrize('state,destination', [('recovery','/account/password'), ('unfinished','/account/profile')])
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
    assert set(client.get_game_genres.call_args.args[0]) == {10, 20}
    client.reset_mock()
    bob_page = bob.get('/discover').get_data(as_text=True)
    assert 'ALICE PRIVATE FAVORITE' not in bob_page and 'ALICE SECRET WISH' not in bob_page
    assert 'On your wishlist' not in bob_page
    assert client.get_game_genres.call_args.args[0] == [11]
    client.reset_mock()
    anon = accounts.test_client().get('/discover')
    assert anon.status_code == 200 and b'Popular picks' in anon.data
    assert b'PRIVATE FAVORITE' not in anon.data and b'SECRET WISH' not in anon.data
    client.get_game_genres.assert_not_called()


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
    client.get_game_genres.assert_not_called()
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
