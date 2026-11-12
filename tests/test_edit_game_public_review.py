"""Existing entries expose the same explicit publication controls as Add game."""

import psycopg
import pytest

from app.db import get_db
from tests.test_accounts import accounts, submit
from tests.test_add_game_public_review import DATA, add
from tests.test_game_reviews import public_author
from tests.test_public_catalog import fake_catalog


def entry_path(app):
    with app.app_context():
        return f"/library/entries/{get_db().execute('SELECT id FROM games ORDER BY id LIMIT 1').fetchone()[0]}/edit"


def test_edit_link_from_catalog_can_publish_an_existing_private_review(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    assert add(client).status_code == 302
    path = entry_path(accounts)
    catalog = client.get('/games/123/portal-2', follow_redirects=True).get_data(as_text=True)
    assert f'href="{path}?from=' in catalog
    editor = client.get(path).get_data(as_text=True)
    assert 'name="publish_review" value="yes">' in editor
    assert DATA['review'] in editor
    response = submit(client, path, {**DATA, 'publish_review': 'yes'})
    assert response.status_code == 303 and response.location.endswith('/games/123/portal-2#your-progress')
    assert b'Saved your changes and published your review.' in client.get(response.location).data
    assert b'Saved your changes and published your review.' not in client.get(response.location).data
    with accounts.app_context():
        assert get_db().execute('SELECT body FROM public_game_reviews').fetchone()[0] == DATA['review']


def test_private_edits_never_overwrite_public_review_without_opt_in(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    add(client, publish_review='yes', public_review_spoilers='yes')
    path = entry_path(accounts)
    assert 'name="public_review_spoilers" value="yes" checked' in client.get(path).get_data(as_text=True)
    assert submit(client, path, {**DATA, 'review': 'Private changes', 'status': 'Completed'}).status_code == 302
    with accounts.app_context():
        assert get_db().execute('SELECT body FROM public_game_reviews').fetchone()[0] == DATA['review']
        assert get_db().execute('SELECT review FROM games').fetchone()[0] == 'Private changes'
    assert submit(client, path, {**DATA, 'review': 'Public changes', 'publish_review': 'yes'}).status_code == 303
    with accounts.app_context():
        row = get_db().execute('SELECT body, has_spoilers FROM public_game_reviews').fetchone()
        assert tuple(row) == ('Public changes', False)
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 1


@pytest.mark.parametrize('changes', [{'rating': ''}, {'review': ''}])
def test_invalid_public_edit_preserves_the_saved_game_and_form_input(accounts, changes):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    add(client)
    response = submit(client, entry_path(accounts), {**DATA, **changes, 'publish_review': 'yes'})
    assert b'role="alert"' in response.data
    assert b'name="publish_review" value="yes" checked' in response.data
    with accounts.app_context():
        assert get_db().execute('SELECT review FROM games').fetchone()[0] == DATA['review']
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_publication_failure_rolls_back_edits_and_preserves_existing_public_review(accounts, monkeypatch):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    add(client, publish_review='yes')
    def fail(*args):
        raise psycopg.DatabaseError('Simulated storage failure')
    monkeypatch.setattr('app.routes.save_public_review', fail)
    response = submit(client, entry_path(accounts), {**DATA, 'review': 'Unsaved changes', 'publish_review': 'yes'})
    assert b'Nothing changed' in response.data
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT review FROM games').fetchone()[0] == DATA['review']
        assert db.execute('SELECT body FROM public_game_reviews').fetchone()[0] == DATA['review']
        assert db.execute('SELECT COUNT(*) FROM public_review_events').fetchone()[0] == 1


def test_other_account_cannot_publish_from_another_players_edit_page(accounts):
    fake_catalog(accounts)
    alice, bob = public_author(accounts, 'alice'), public_author(accounts, 'bob')
    add(alice)
    path = entry_path(accounts)
    assert bob.get(path).status_code == 404
    assert submit(bob, path, {**DATA, 'publish_review': 'yes'}, source='/library/add').status_code == 404
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_edit_can_delete_public_review_without_saving_pending_private_changes(accounts):
    fake_catalog(accounts)
    client = public_author(accounts, 'alice')
    add(client, publish_review='yes')
    path = entry_path(accounts)
    editor = client.get(path).get_data(as_text=True)
    action = '/explore/games/123/reviews/delete'
    assert f'formaction="{action}" formnovalidate>Delete public review' in editor
    response = submit(client, action, {**DATA, 'review': 'Unsaved changes'}, source=path)
    assert response.status_code == 303
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0
        assert get_db().execute('SELECT review FROM games').fetchone()[0] == DATA['review']
    assert 'Delete public review' not in client.get(path).get_data(as_text=True)
