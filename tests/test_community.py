"""Only the activated-account aggregate is publicly visible."""
from unittest.mock import Mock

import psycopg

from app.community import member_count
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


def test_member_count_is_public_cached_and_counts_each_confirmed_identity_once(accounts, monkeypatch):
    clock = [100]
    monkeypatch.setattr('app.community.monotonic', lambda: clock[0])
    client = accounts.test_client()
    assert client.get('/community/member-count').json == {'count': 0}
    guest = client.get('/').get_data(as_text=True)
    assert 'data-member-count-value>0</span>' in guest
    sign_in(accounts, 'alice')
    sign_in(accounts, 'alice')
    assert client.get('/community/member-count').json == {'count': 0}
    clock[0] += 61
    response = client.get('/community/member-count')
    assert response.status_code == 200 and response.json == {'count': 1}
    assert 'no-store' in response.headers['Cache-Control']
    submit(client, '/account/register', {'email':'bob@example.test','password':'test-password','confirmation':'test-password'})
    clock[0] += 61
    assert client.get('/community/member-count').json == {'count': 1}
    sign_in(accounts, 'bob')
    clock[0] += 61
    assert client.get('/community/member-count').json == {'count': 2}
    accounts.config['PUBLIC_MEMBER_COUNT_EXCLUDED_IDS'] = ALICE + ',' + BOB
    clock[0] += 61
    assert client.get('/community/member-count').json == {'count': 0}
    assert 'alice@example.test' not in guest and 'alice-access' not in guest


def test_unavailable_member_count_never_breaks_home_or_publishes_a_fake_zero(accounts, monkeypatch):
    clock = [100]
    monkeypatch.setattr('app.community.monotonic', lambda: clock[0])
    database = Mock()
    database.execute.side_effect = psycopg.OperationalError('private connection detail')
    monkeypatch.setattr('app.community.get_db', lambda: database)
    client = accounts.test_client()
    response = client.get('/community/member-count')
    assert response.status_code == 503 and response.json == {'count': None}
    page = client.get('/')
    assert page.status_code == 200 and 'private connection' not in page.get_data(as_text=True)
    assert 'data-member-count-value></span>' in page.get_data(as_text=True)
    assert database.execute.call_count == 1
    database.execute.side_effect = None
    database.execute.return_value.fetchone.return_value = {'total': 4}
    clock[0] += 61
    assert client.get('/community/member-count').json == {'count': 4}


def test_offline_installations_do_not_query_account_tables(app, monkeypatch):
    def forbidden():
        raise AssertionError('No account database in offline mode')
    monkeypatch.setattr('app.community.get_db', forbidden)
    with app.app_context():
        assert member_count() is None
    assert app.test_client().get('/community/member-count').status_code == 503
