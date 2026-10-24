"""Public review consent, isolation, moderation, and rendering boundaries."""

from uuid import uuid4

import pytest

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_public_catalog import fake_catalog


PATH = '/explore/games/123'
DATA = {'body': 'A memorable journey.', 'rating': '9'}


def public_author(app, name):
    client = sign_in(app, name)
    assert submit(client, '/account/profile/sharing', {'username': name + '_player', 'is_public': 'yes'}).status_code == 303
    return client


def publish(client, data=None):
    return submit(client, PATH, DATA if data is None else data, source=PATH)


def review_id(app):
    with app.app_context():
        return get_db().execute('SELECT id FROM public_game_reviews ORDER BY id LIMIT 1').fetchone()[0]


def test_publication_is_explicit_and_never_changes_or_copies_private_notes(accounts):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    with accounts.app_context():
        get_db().execute("INSERT INTO games (title, platform, review, rating, owner_id, igdb_id) VALUES ('Portal', 'PC', 'SECRET PERSONAL NOTE', 3, ?, 123)", (ALICE,))
    assert 'SECRET PERSONAL NOTE' not in accounts.test_client().get(PATH).get_data(as_text=True)
    assert publish(alice).status_code == 303
    html = accounts.test_client().get(PATH).get_data(as_text=True)
    assert DATA['body'] in html and '4.5/5' in html
    assert '/profile/alice_player' in html
    for private in ('SECRET PERSONAL NOTE', ALICE, 'alice@example.test', 'alice-access'):
        assert private not in html
    assert publish(alice, {'body': 'Updated opinion.', 'rating': '7'}).status_code == 303
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 1
        assert tuple(db.execute('SELECT review, rating FROM games').fetchone()) == ('SECRET PERSONAL NOTE', 3)
    assert DATA['body'] not in accounts.test_client().get(PATH).get_data(as_text=True)


@pytest.mark.parametrize('changes', [{'rating': ''}, {'rating': '0'}, {'rating': '11'}, {'rating': '2.5'}, {'body': '  '}, {'body': 'x' * 2001}, {'body': 'bad\x00text'}])
def test_invalid_review_keeps_input_and_never_publishes(accounts, changes):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    response = publish(alice, {**DATA, **changes})
    assert response.status_code == 400
    assert b'role="alert"' in response.data and b'id="write-review" open' in response.data
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_unknown_catalog_game_does_not_accept_reviews(accounts):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    response = submit(alice, '/explore/games/999', DATA, source=PATH)
    assert response.status_code == 404
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_reviews_are_visible_directly_with_spoiler_labels_and_escaped_html(accounts):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    body = '<script>alert(1)</script>' + ' A very long memory.' * 50
    assert publish(alice, {**DATA, 'body': body, 'has_spoilers': 'yes'}).status_code == 303
    html = accounts.test_client().get(PATH).get_data(as_text=True)
    assert '<details class="community-review-content">' not in html
    assert 'Spoilers</span>' in html and 'Show review' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '<script>alert(1)</script>' not in html
    assert publish(alice, {**DATA, 'body': body}).status_code == 303
    html = accounts.test_client().get(PATH).get_data(as_text=True)
    assert 'Read full review' not in html
    assert 'class="community-spoiler-label"' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html


def test_author_binding_private_profile_visibility_and_owner_only_deletion(accounts):
    fake_catalog(accounts)
    alice, bob = public_author(accounts, 'alice'), public_author(accounts, 'bob')
    assert publish(alice, {**DATA, 'owner_id': BOB, 'username': 'bob_player'}).status_code == 303
    assert submit(bob, PATH + '/reviews/delete', {}, source=PATH).status_code == 303
    assert DATA['body'] in accounts.test_client().get(PATH).get_data(as_text=True)
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET is_public = FALSE WHERE id = ?', (ALICE,))
    assert DATA['body'] not in accounts.test_client().get(PATH).get_data(as_text=True)
    assert publish(alice).status_code == 400
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET is_public = TRUE WHERE id = ?', (ALICE,))
    assert DATA['body'] in accounts.test_client().get(PATH).get_data(as_text=True)
    assert submit(alice, PATH + '/reviews/delete', {}, source=PATH).status_code == 303
    assert DATA['body'] not in accounts.test_client().get(PATH).get_data(as_text=True)


def test_guest_recovery_incomplete_and_csrf_cannot_publish(accounts):
    fake_catalog(accounts)
    guest = accounts.test_client()
    response = submit(guest, PATH, DATA, source='/account/login')
    assert response.location.endswith('/account/login')
    alice = public_author(accounts, 'alice')
    assert alice.post(PATH, data=DATA).status_code == 400
    incomplete = sign_in(accounts, 'bob', complete_profile=False)
    assert '/profile/edit' in publish(incomplete).location
    with accounts.app_context():
        get_db().execute('UPDATE account_sessions SET recovery = 1 WHERE user_id = ?', (ALICE,))
    assert publish(alice).location.endswith('/account/password')
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_report_hides_for_reporter_only_and_is_idempotent(accounts):
    fake_catalog(accounts)
    alice, bob = public_author(accounts, 'alice'), public_author(accounts, 'bob')
    publish(alice)
    rid = review_id(accounts)
    endpoint = f'{PATH}/reviews/{rid}/report'
    assert submit(alice, endpoint, {'reason': 'spam'}, source=PATH).status_code == 404
    assert submit(bob, endpoint, {'reason': 'invalid'}, source=PATH).status_code == 400
    assert submit(bob, f'/explore/games/124/reviews/{rid}/report', {'reason': 'spam'}, source=PATH).status_code == 404
    for _ in range(2):
        assert submit(bob, endpoint, {'reason': 'abuse'}, source=PATH).status_code == 303
    assert DATA['body'] not in bob.get(PATH).get_data(as_text=True)
    assert DATA['body'] in accounts.test_client().get(PATH).get_data(as_text=True)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_review_reports').fetchone()[0] == 1
    report_list = accounts.test_cli_runner().invoke(args=['review-reports'])
    assert report_list.exit_code == 0 and f'Review {rid}' in report_list.output
    assert BOB not in report_list.output
    assert bob.post(endpoint, data={'reason': 'spam'}).status_code == 400


def test_write_budget_is_persistent_but_never_prevents_deleting_your_review(accounts):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    publish(alice)
    with accounts.app_context():
        for _ in range(29):
            get_db().execute('INSERT INTO public_review_events (owner_id) VALUES (?)', (ALICE,))
    response = publish(alice, {**DATA, 'body': 'Blocked update'})
    assert response.status_code == 400 and b'too many review changes' in response.data
    assert submit(alice, PATH + '/reviews/delete', {}, source=PATH).status_code == 303


def test_moderation_is_operator_only_and_edits_cannot_evade_it(accounts):
    fake_catalog(accounts)
    alice = public_author(accounts, 'alice')
    publish(alice)
    rid = review_id(accounts)
    runner = accounts.test_cli_runner()
    assert runner.invoke(args=['moderate-review', '--review-id', str(rid)]).exit_code == 0
    assert DATA['body'] in accounts.test_client().get(PATH).get_data(as_text=True)
    assert runner.invoke(args=['moderate-review', '--review-id', str(rid), '--apply']).exit_code == 0
    assert DATA['body'] not in accounts.test_client().get(PATH).get_data(as_text=True)
    assert publish(alice, {**DATA, 'body': 'Trying to republish', 'moderation_hidden': 'false'}).status_code == 303
    assert 'Trying to republish' not in accounts.test_client().get(PATH).get_data(as_text=True)
    assert runner.invoke(args=['moderate-review', '--review-id', str(rid), '--restore', '--apply']).exit_code == 0
    assert 'Trying to republish' in accounts.test_client().get(PATH).get_data(as_text=True)


def test_review_pagination_average_and_storage_security(accounts):
    fake_catalog(accounts)
    with accounts.app_context():
        db = get_db()
        for index in range(11):
            owner = str(uuid4())
            db.execute('INSERT INTO profiles (id, display_name) VALUES (?, ?)', (owner, f'Reviewer {index}'))
            db.execute('INSERT INTO profile_usernames (username, owner_id) VALUES (?, ?)', (f'reviewer_{index}', owner))
            db.execute('UPDATE profiles SET username = ?, is_public = TRUE WHERE id = ?', (f'reviewer_{index}', owner))
            db.execute('INSERT INTO public_game_reviews (catalog_id, owner_id, rating, body) VALUES (123, ?, 7, ?)',
                       (owner, f'Public opinion number {index}.'))
        for table in ('public_game_reviews', 'public_review_reports', 'public_review_events'):
            assert db.execute('SELECT relrowsecurity FROM pg_class WHERE oid = ?::regclass', (table,)).fetchone()[0]
    guest = accounts.test_client()
    first = guest.get(PATH).get_data(as_text=True)
    assert first.count('class="community-review"') == 10
    assert '3.5<small>/5' in first and 'Older reviews' in first
    second = guest.get(PATH + '?reviews_page=2').get_data(as_text=True)
    assert second.count('class="community-review"') == 1 and 'Newer reviews' in second
    for page in ('0', '-1', 'no', '10001'):
        assert guest.get(PATH + '?reviews_page=' + page).status_code == 400
