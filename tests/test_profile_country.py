"""Country identity remains optional, owner-scoped, and explicitly shared."""

from pathlib import Path

import psycopg
import pytest

from app.countries import COUNTRIES, clean_country
from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


EDIT = '/account/profile/edit'
SHARING = '/account/profile/sharing'


def test_country_allowlist_and_local_assets():
    assert len(COUNTRIES) == 249
    assert clean_country(' cl ') == 'CL'
    assert clean_country('') is None
    for code in ('XX', '../cl', '<script>', 'Chile', 'USA'):
        with pytest.raises(ValueError):
            clean_country(code)
    flags = Path(__file__).resolve().parents[1] / 'app/static/images/flags'
    assert all((flags / (item['code'].lower() + '.svg')).is_file() for item in COUNTRIES)


def test_setup_country_is_optional_and_never_shared_implicitly(accounts):
    alice = sign_in(accounts, 'alice', complete_profile=False)
    result = submit(alice, EDIT, {'display_name': 'Alice', 'username': 'alice_player', 'country_code': 'cl'})
    assert result.status_code == 303
    private = alice.get(result.location).get_data(as_text=True)
    assert 'images/flags/cl.svg' in private and 'alt="Chile"' in private
    anon = accounts.test_client()
    assert 'images/flags/cl.svg' not in anon.get('/players/alice_player').get_data(as_text=True)
    with accounts.app_context():
        row = get_db().execute('SELECT country_code, share_country FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert row['country_code'] == 'CL' and not row['share_country']


def test_country_changes_and_removal_are_scoped_and_validated(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    assert submit(alice, EDIT, {'display_name': 'Alice', 'country_code': 'CL', 'share_country': 'yes', 'user_id': BOB}).status_code == 303
    response = submit(alice, EDIT, {'display_name': 'Must roll back', 'country_code': '../cl'})
    assert response.status_code == 200 and 'Choose a country from the list' in response.get_data(as_text=True)
    with accounts.app_context():
        db = get_db()
        row = db.execute('SELECT display_name, country_code, share_country FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert row['display_name'] == 'Alice' and row['country_code'] == 'CL' and row['share_country']
        assert db.execute('SELECT country_code FROM profiles WHERE id = ?', (BOB,)).fetchone()[0] is None
        with pytest.raises(psycopg.IntegrityError):
            db.execute("UPDATE profiles SET country_code = 'XX' WHERE id = ?", (ALICE,))
    assert submit(alice, EDIT, {'display_name': 'Alice', 'country_code': ''}).status_code == 303
    assert 'images/flags/cl.svg' not in alice.get('/account/profile', follow_redirects=True).get_data(as_text=True)
    assert alice.post(EDIT, data={'display_name': 'Alice', 'country_code': 'US'}).status_code == 400


def test_public_flag_requires_both_visibility_and_country_consent(accounts):
    alice = sign_in(accounts, 'alice')
    submit(alice, EDIT, {'display_name': 'Alice', 'country_code': 'CL'})
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes', 'share_country': 'yes'})
    anon = accounts.test_client()
    public = anon.get('/players/alice_player')
    assert public.status_code == 200 and 'images/flags/cl.svg' in public.get_data(as_text=True)
    assert public.headers['Cache-Control'] == 'private, no-store'
    # The editor reflects the same consent and can change the shared country.
    assert 'name="share_country" value="yes" checked' in alice.get(EDIT, follow_redirects=True).get_data(as_text=True)
    submit(alice, EDIT, {'display_name': 'Alice', 'country_code': 'JP', 'share_country': 'yes'})
    assert 'images/flags/jp.svg' in anon.get('/players/alice_player').get_data(as_text=True)
    submit(alice, SHARING, {'username': 'alice_player', 'is_public': 'yes'})
    assert 'images/flags/jp.svg' not in anon.get('/players/alice_player').get_data(as_text=True)
    submit(alice, SHARING, {'username': 'alice_player', 'share_country': 'yes'})
    assert anon.get('/players/alice_player').status_code == 404
    assert 'images/flags/jp.svg' in alice.get('/account/profile', follow_redirects=True).get_data(as_text=True)
