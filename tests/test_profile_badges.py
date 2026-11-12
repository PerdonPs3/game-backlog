"""Cosmetic Creator badges are server-assigned, account-bound, and respect privacy."""

from app import create_app
from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit


def test_badge_assignment_is_explicit_and_account_bound(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    submit(alice, '/account/profile/sharing', {'username': 'm4ckay', 'is_public': 'yes'})
    submit(bob, '/account/profile/sharing', {'username': 'other_player', 'is_public': 'yes'})
    runner = accounts.test_cli_runner()
    args = ['set-admin-badge', '--username', 'm4ckay']
    assert runner.invoke(args=args).exit_code == 0
    assert 'profile-admin-badge' not in alice.get('/account/profile', follow_redirects=True).get_data(as_text=True)
    assert runner.invoke(args=[*args, '--apply']).exit_code == 0
    for path in ('/account/profile', '/settings/profile', '/players/m4ckay'):
        assert 'class="profile-admin-badge"' in alice.get(path, follow_redirects=True).get_data(as_text=True)
    public = accounts.test_client().get('/players/m4ckay')
    assert 'class="profile-admin-badge"' in public.get_data(as_text=True)
    assert '<span>Creator</span>' in public.get_data(as_text=True)
    assert 'class="profile-admin-badge"' not in accounts.test_client().get('/players/other_player').get_data(as_text=True)
    # A rename preserves the badge because it belongs to the immutable account ID.
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET username_changed_at = NULL WHERE id = ?', (ALICE,))
    submit(alice, '/account/profile/sharing', {'username': 'renamed_player', 'is_public': 'yes'})
    assert 'class="profile-admin-badge"' in accounts.test_client().get('/players/renamed_player').get_data(as_text=True)
    assert runner.invoke(args=[*args, '--apply']).exit_code != 0
    assert runner.invoke(args=['set-admin-badge', '--username', 'renamed_player', '--remove', '--apply']).exit_code == 0
    assert 'class="profile-admin-badge"' not in accounts.test_client().get('/players/renamed_player').get_data(as_text=True)


def test_forms_cannot_assign_or_remove_badges_or_publish_private_profiles(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    submit(alice, '/account/profile/sharing', {'username': 'm4ckay'})
    runner = accounts.test_cli_runner()
    assert runner.invoke(args=['set-admin-badge', '--username', 'm4ckay', '--apply']).exit_code == 0
    submit(alice, '/settings/profile', {'display_name': 'Alice', 'admin_badge': 'no'})
    submit(bob, '/settings/profile', {'display_name': 'Bob', 'admin_badge': 'yes', 'user_id': ALICE})
    submit(bob, '/account/profile/sharing', {'username': 'other_player', 'is_public': 'yes', 'admin_badge': 'yes'})
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT admin_badge FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0]
        assert not db.execute('SELECT admin_badge FROM profiles WHERE id = ?', (BOB,)).fetchone()[0]
    assert accounts.test_client().get('/players/m4ckay').status_code == 404
    assert 'class="profile-admin-badge"' in alice.get('/settings/profile', follow_redirects=True).get_data(as_text=True)


def test_badge_command_requires_hosted_database(tmp_path):
    offline = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': str(tmp_path / 'offline.sqlite')})
    result = offline.test_cli_runner().invoke(args=['set-admin-badge', '--username', 'm4ckay', '--apply'])
    assert result.exit_code != 0 and 'requires PostgreSQL' in result.output
