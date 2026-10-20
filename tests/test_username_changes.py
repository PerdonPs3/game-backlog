"""Exercise username cooldown boundaries, shared reservations, and revocable aliases."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.db import get_db
import app.public_profiles as profiles
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


PATH = '/account/profile/sharing'
START = 1800000000
WAIT = 30 * 86400


@pytest.fixture
def clock(monkeypatch):
    now = [START]
    monkeypatch.setattr(profiles, 'username_clock', lambda db: now[0])
    return now


def test_exact_cooldown_boundary_and_aliases_point_directly_to_current_public_name(accounts, clock):
    alice = sign_in(accounts, 'alice')
    submit(alice, PATH, {'username':'first_name', 'is_public':'yes'})
    clock[0] += WAIT - 1
    denied = submit(alice, PATH, {'username':'second_name', 'is_public':'no'})
    assert 'change your username again on' in denied.get_data(as_text=True)
    assert accounts.test_client().get('/players/first_name').status_code == 200
    clock[0] += 1
    assert submit(alice, PATH, {'username':'second_name', 'is_public':'yes'}).status_code == 303
    anon = accounts.test_client()
    old = anon.get('/players/first_name')
    assert old.status_code == 302 and old.location.endswith('/players/second_name')
    assert old.headers['Cache-Control'] == 'private, no-store'
    assert 'noindex' in old.headers['X-Robots-Tag']
    clock[0] += WAIT
    assert submit(alice, PATH, {'username':'third_name', 'is_public':'yes'}).status_code == 303
    for name in ('first_name','second_name'):
        assert anon.get('/players/'+name).location.endswith('/players/third_name')
    assert '@third_name' in anon.get('/players/first_name', follow_redirects=True).get_data(as_text=True)
    submit(alice, PATH, {'username':'third_name', 'is_public':'no'})
    for name in ('first_name','second_name','third_name'):
        assert anon.get('/players/'+name).status_code == 404
        assert alice.get('/players/'+name).status_code == 404


def test_sharing_changes_and_capitalization_do_not_extend_wait(accounts, clock):
    alice = sign_in(accounts, 'alice')
    submit(alice, PATH, {'username':'Current_Name', 'is_public':'yes'})
    clock[0] += 2 * 86400
    assert submit(alice, PATH, {'username':'CURRENT_NAME','share_bio':'yes','share_showcase':'yes'}).status_code == 303
    with accounts.app_context():
        row = get_db().execute('SELECT username_changed_at, is_public, share_bio FROM profiles WHERE id = ?', (ALICE,)).fetchone()
        assert row['username_changed_at'] == START and not row['is_public'] and row['share_bio']
    page = alice.get(PATH).get_data(as_text=True)
    assert 'readonly' in page and 'You can change your username again on' in page and 'datetime=' in page
    assert 'Permanent' not in page
    clock[0] = START + WAIT
    assert 'name="username"' in alice.get(PATH).get_data(as_text=True)
    assert 'readonly' not in alice.get(PATH).get_data(as_text=True)


def test_aliases_cannot_be_taken_by_other_accounts_but_owner_can_reuse_them(accounts, clock):
    alice, bob = sign_in(accounts,'alice'), sign_in(accounts,'bob',complete_profile=False)
    submit(alice,PATH,{'username':'old_name','is_public':'yes'})
    clock[0] += WAIT
    submit(alice,PATH,{'username':'new_name','is_public':'yes'})
    denied=submit(bob,'/account/profile/edit',{'display_name':'Bob','username':'OLD_NAME'})
    assert 'already taken or reserved' in denied.get_data(as_text=True)
    with accounts.app_context():
        assert get_db().execute('SELECT display_name FROM profiles WHERE id = ?', (BOB,)).fetchone()[0] == ''
    submit(bob,'/account/profile/edit',{'display_name':'Bob','username':'bob_player'})
    clock[0] += WAIT
    denied=submit(bob,PATH,{'username':'old_name','is_public':'yes'})
    assert 'already taken or reserved' in denied.get_data(as_text=True)
    assert submit(alice,PATH,{'username':'old_name','is_public':'yes'}).status_code == 303
    anon=accounts.test_client()
    assert anon.get('/players/old_name').status_code == 200
    assert anon.get('/players/new_name').location.endswith('/players/old_name')


def test_concurrent_claims_have_one_winner_without_partial_profile_updates(accounts, clock):
    alice,bob=sign_in(accounts,'alice'),sign_in(accounts,'bob')
    submit(alice,PATH,{'username':'alice_before'})
    submit(bob,PATH,{'username':'bob_before'})
    clock[0] += WAIT
    barrier=Barrier(2)
    def claim(owner):
        with accounts.app_context():
            barrier.wait(timeout=10)
            try:
                profiles.save_sharing(get_db(),owner,{'username':'contested_name','is_public':'yes'})
                return True
            except ValueError:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(claim,(ALICE,BOB)))
    assert sum(outcomes)==1
    winner=ALICE if outcomes[0] else BOB
    with accounts.app_context():
        db=get_db()
        assert str(db.execute("SELECT owner_id FROM profile_usernames WHERE username = 'contested_name'").fetchone()[0]) == winner
        for owner,original in ((ALICE,'alice_before'),(BOB,'bob_before')):
            row=db.execute('SELECT username, username_changed_at, is_public FROM profiles WHERE id = ?', (owner,)).fetchone()
            assert row['username']==('contested_name' if owner==winner else original)
            assert row['username_changed_at']==(clock[0] if owner==winner else START)
            assert row['is_public']==(owner==winner)
