from unittest.mock import Mock

import pytest

from app.catalog import CatalogError
from app.db import get_db
from app.library_picker import preference_games, recommend
from tests.test_accounts import accounts, libraries


def game(entry_id, catalog_id, rating=None, title='Example'):
    return {'id': entry_id, 'igdb_id': catalog_id, 'rating': rating, 'title': title}


def test_preference_signals_are_bounded_and_do_not_count_platform_copies_twice():
    rows = [game(i, i, 10) for i in range(1, 80)]
    rows += [game(100, 79, 2), game(101, 78, 6), game(102, None, 10)]
    signals = preference_games(rows)
    assert len(signals) == 60
    assert signals[0]['rating'] == 2
    assert len({row['igdb_id'] for row in signals}) == 60
    assert 78 not in {row['igdb_id'] for row in signals}


def test_recommendations_use_positive_genres_and_explain_the_matching_rating():
    puzzle, shooter = game(1, 10), game(2, 20)
    source = game(3, 30, 9, 'Favorite puzzle')
    pool, reasons = recommend([puzzle, shooter], [source], {10: ('Puzzle',), 20: ('Shooter',), 30: ('Puzzle',)})
    assert pool == [puzzle]
    assert reasons[1] == {'title': 'Favorite puzzle', 'rating': 9, 'genres': ['Puzzle']}


def test_low_ratings_reduce_matches_and_a_candidate_never_recommends_itself():
    puzzle, shooter = game(1, 10), game(2, 20)
    signals = [game(3, 30, 8), game(4, 40, 1), game(5, 20, 10)]
    genres = {10: ('Puzzle',), 20: ('Shooter',), 30: ('Puzzle', 'Shooter'), 40: ('Puzzle',)}
    pool, _ = recommend([puzzle, shooter], signals, genres)
    assert pool == [shooter]
    assert recommend([shooter], [game(6, 20, 10)], genres) == ([], {})


def test_missing_genres_and_no_positive_evidence_leave_an_explicit_random_fallback():
    assert recommend([game(1, None)], [game(2, 30, 10)], {30: ('Puzzle',)}) == ([], {})
    assert recommend([game(1, 10)], [game(2, 30, 2)], {10: ('Puzzle',), 30: ('Puzzle',)}) == ([], {})


def test_equal_matches_remain_tied_instead_of_claiming_a_unique_recommendation():
    candidates = [game(1, 10), game(2, 20)]
    pool, _ = recommend(candidates, [game(3, 30, 10)], {10: ('Puzzle',), 20: ('Puzzle',), 30: ('Puzzle',)})
    assert pool == candidates


def test_explanation_only_uses_genres_with_positive_net_evidence():
    candidate = game(1, 10)
    sources = [game(2, 20, 10, 'Great puzzle'), game(3, 30, 8, 'Great shooter'), game(4, 40, 1)]
    genres = {10: ('Puzzle', 'Shooter'), 20: ('Puzzle',), 30: ('Shooter',), 40: ('Puzzle',)}
    pool, reasons = recommend([candidate], sources, genres)
    assert pool == [candidate]
    assert reasons[1]['title'] == 'Great shooter'
    assert reasons[1]['genres'] == ['Shooter']


def link(app, entry, catalog_id, rating=None):
    with app.app_context():
        db = get_db()
        db.execute('UPDATE games SET igdb_id = ?, rating = ? WHERE id = ?', (catalog_id, rating, entry))
        db.commit()


def test_selected_states_define_the_pool_and_repeat_links_preserve_them(client, seed_game, stored_games):
    seed_game(title='Continue this', status='Playing')
    seed_game(title='Resume this', status='On hold')
    seed_game(title='Do not replay', status='Completed')
    seed_game(title='Not this backlog', status='Backlog')
    before = stored_games()
    response = client.get('/games/pick', query_string={'pick': '1', 'mode': 'random', 'status': ['Playing', 'On hold']})
    assert response.status_code == 200
    assert b'2 matching entries' in response.data
    assert b'Do not replay' not in response.data and b'Not this backlog' not in response.data
    assert b'status=Playing' in response.data and b'status=On+hold' in response.data
    assert stored_games() == before


def test_completed_games_require_explicit_selection(client, seed_game):
    seed_game(title='Replay me', status='Completed')
    assert b'Replay me' not in client.get('/games/pick?pick=1').data
    assert b'Replay me' in client.get('/games/pick?pick=1&status=Completed').data


def test_deselecting_every_state_never_silently_uses_backlog(app, client, seed_game):
    seed_game(title='Hidden pending game', status='Backlog')
    provider = Mock()
    app.extensions['igdb_client'] = provider
    response = client.get('/games/pick?pick=1&status_filter=1&genre=Puzzle')
    assert response.status_code == 200
    assert b'Choose at least one status.' in response.data
    assert b'Hidden pending game' not in response.data
    provider.get_game_genres.assert_not_called()


@pytest.mark.parametrize('query', [{'status': 'Invalid'}, {'mode': 'secret'}, {'status': ['Backlog'] * 6}])
def test_invalid_modes_and_states_are_rejected(client, query):
    assert client.get('/games/pick', query_string=query).status_code == 400


def recommendation_library(app, seed_game):
    favorite = seed_game(title='<Favorite puzzle>', status='Completed')
    puzzle = seed_game(title='Next puzzle', status='Backlog')
    shooter = seed_game(title='Other shooter', status='Backlog')
    for entry, catalog_id, rating in [(favorite, 300, 10), (puzzle, 100, None), (shooter, 200, None)]:
        link(app, entry, catalog_id, rating)
    provider = app.extensions['igdb_client']
    provider.get_game_genres.return_value = {100: ('Puzzle',), 200: ('Shooter',), 300: ('Puzzle',)}
    return provider


def test_personalized_pick_explains_the_evidence_and_keeps_the_library_unchanged(app, client, seed_game, stored_games):
    recommendation_library(app, seed_game)
    before = stored_games()
    response = client.get('/games/pick?pick=1')
    assert b'Recommended for you' in response.data and b'Next puzzle' in response.data
    assert b'Why this pick' in response.data and b'5/5' in response.data
    assert b'id="roulette-data"' not in response.data
    assert b'&lt;Favorite puzzle&gt;' in response.data
    assert b'<Favorite puzzle>' not in response.data and b'Other shooter' not in response.data
    assert stored_games() == before
    assert response.headers['Cache-Control'] == 'no-store'


def test_random_mode_does_not_apply_ratings_or_fetch_preference_genres(app, client, seed_game, monkeypatch):
    provider = recommendation_library(app, seed_game)
    monkeypatch.setattr('app.routes.choice', lambda rows: rows[-1])
    response = client.get('/games/pick?pick=1&mode=random')
    assert b'Other shooter' in response.data and b'Why this pick' not in response.data
    assert b'id="roulette-data"' in response.data
    provider.get_game_genres.assert_called_once_with({100, 200})


def test_recommendation_outage_uses_a_disclosed_random_fallback(app, client, seed_game):
    provider = recommendation_library(app, seed_game)
    provider.get_game_genres.side_effect = CatalogError('Sensitive provider failure')
    response = client.get('/games/pick?pick=1')
    assert response.status_code == 200
    assert b'This is a random pick' in response.data and b'Why this pick' not in response.data
    assert b'Sensitive provider failure' not in response.data
    assert b'We could not check this genre' in client.get('/games/pick?pick=1&genre=Puzzle').data


def test_other_accounts_never_supply_preference_signals_or_catalog_requests(accounts, libraries):
    alice, _, ids = libraries
    with accounts.app_context():
        db = get_db()
        db.execute('UPDATE games SET igdb_id = 100 WHERE id = ?', (ids['alice'][0],))
        db.execute("UPDATE games SET igdb_id = 200, rating = 10, status = 'Completed' WHERE id = ?", (ids['bob'][0],))
        db.commit()
    provider = Mock()
    provider.get_game_genres.return_value = {100: ('Puzzle',), 200: ('Puzzle',)}
    accounts.extensions['igdb_client'] = provider
    response = alice.get('/games/pick?pick=1')
    assert response.status_code == 200
    assert b'bob secret game' not in response.data and b'Why this pick' not in response.data
    provider.get_game_genres.assert_called_once_with({100})


def test_async_random_draw_returns_only_safe_outcome_with_native_fallback(client, seed_game, stored_games):
    seed_game(title='<script>Private adventure</script>', status='Playing')
    before = stored_games()
    response = client.get('/games/pick?pick=1&mode=random&status=Playing', headers={'Accept': 'application/json'})
    assert response.status_code == 200
    assert response.is_json
    data = response.get_json()
    assert 'adventure-roulette' in data['html']
    assert 'data-pick-again' in data['html']
    assert '&lt;script&gt;Private adventure&lt;/script&gt;' in data['html']
    assert '<script>Private adventure</script>' not in data['html']
    assert '<form' not in data['html'] and '<!DOCTYPE' not in data['html']
    assert data['genres'] == []
    assert 'no-store' in response.headers['Cache-Control']
    assert stored_games() == before
    assert b'adventure-preferences' in client.get('/games/pick').data
