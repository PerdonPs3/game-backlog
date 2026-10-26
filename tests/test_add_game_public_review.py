"""Library creation can explicitly publish the same review in one transaction."""

import psycopg
import pytest

from app.db import get_db
from tests.test_accounts import ALICE, accounts, sign_in, submit
from tests.test_game_reviews import public_author
from tests.test_public_catalog import fake_catalog


DATA = {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Playing',
        'rating': '9', 'review': 'A journey worth sharing.'}


def add(client, **changes):
    return submit(client, '/games/new', {**DATA, **changes}, source='/games/new?igdb_id=123')


def test_add_game_defaults_to_private_notes(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    html = client.get('/games/new?igdb_id=123').get_data(as_text=True)
    assert 'name="publish_review" value="yes">' in html
    assert add(client).status_code == 302
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_opt_in_creates_both_records_and_explicitly_updates_existing_public_review(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    response = add(client, publish_review='yes', public_review_spoilers='yes', owner_id='forged')
    assert response.status_code == 303 and response.location.endswith('/account/alice_player/library')
    assert b'Added to your library and published your review.' in client.get(response.location).data
    assert b'Added to your library and published your review.' not in client.get(response.location).data
    with accounts.app_context():
        db = get_db()
        assert tuple(db.execute('SELECT review, rating FROM games').fetchone()) == (DATA['review'], 9)
        row = db.execute('SELECT body, rating, has_spoilers, owner_id FROM public_game_reviews').fetchone()
        assert tuple(row) == (DATA['review'], 9, True, row['owner_id'])
        assert str(row['owner_id']) == ALICE
    assert add(client, publish_review='yes', platform='PS3', review='Updated from another platform.').status_code == 303
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 1
        assert db.execute('SELECT body FROM public_game_reviews').fetchone()[0] == 'Updated from another platform.'


@pytest.mark.parametrize('changes', [{'rating': ''}, {'review': ''}, {'review': 'bad\x00text'}])
def test_invalid_publication_keeps_form_values_without_creating_game(accounts, changes):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    response = add(client, publish_review='yes', **changes)
    assert response.status_code == 200 and b'role="alert"' in response.data
    assert b'name="publish_review" value="yes" checked' in response.data
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_private_profile_cannot_publish_but_can_keep_notes_private(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    response = add(client, publish_review='yes')
    assert b'A public profile is required' in response.data
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
    assert add(client).status_code == 302


def test_duplicate_never_overwrites_an_existing_public_review(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    assert add(client, publish_review='yes').status_code == 303
    assert b'already in your collection' in add(client, publish_review='yes', review='Duplicate attempt').data
    with accounts.app_context():
        assert get_db().execute('SELECT body FROM public_game_reviews').fetchone()[0] == DATA['review']


def test_publication_failure_rolls_back_the_game_and_rate_budget(accounts, monkeypatch):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    def fail(*args):
        raise psycopg.DatabaseError('Simulated storage failure')
    monkeypatch.setattr('app.routes.save_public_review', fail)
    response = add(client, publish_review='yes')
    assert b'Nothing changed' in response.data
    with accounts.app_context():
        db = get_db()
        for table in ('games', 'public_game_reviews', 'public_review_events'):
            assert db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0


def test_rate_limit_and_missing_csrf_never_create_partial_records(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    assert client.post('/games/new', data={**DATA, 'publish_review': 'yes'}).status_code == 400
    with accounts.app_context():
        for _ in range(30):
            get_db().execute('INSERT INTO public_review_events (owner_id) VALUES (?)', (ALICE,))
    assert b'too many review changes' in add(client, publish_review='yes').data
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_publishing_from_catalog_add_flow_returns_to_library(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    response = add(client, publish_review='yes', return_to_catalog='yes')
    assert response.status_code == 303
    assert response.location.endswith('/account/alice_player/library')
    assert b'Added to your library and published your review.' in client.get(response.location).data
