"""Wishlist privacy, ownership, provider failures, and atomic library transfers."""

import psycopg
import pytest

from app import create_app
from app.catalog import CatalogError
from app.db import get_db
import app.migrations as migrations
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_backups import backup_entry, encoded, import_file
from tests.conftest import CSRFTokenParser
from tests.test_public_catalog import fake_catalog


def save(client, catalog_id=123, **extra):
    return submit(client, f'/wishlist/games/{catalog_id}/add', extra, source='/library/wishlist')


def saved(app, owner=ALICE):
    with app.app_context():
        return get_db().execute('SELECT catalog_id,title,cover_image_id FROM wishlist_games WHERE owner_id = ? ORDER BY catalog_id', (owner,)).fetchall()


def publish(client, name='alice_player', share='yes'):
    return submit(client, '/account/profile/sharing', {'username': name, 'is_public': 'yes', 'wishlist_controls': 'yes', 'share_wishlist': share})


def test_save_is_public_by_default_idempotent_and_never_creates_an_owned_game_or_badge(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    response = save(alice, owner_id=BOB, title='<script>forged</script>', cover_image_id='evil')
    assert response.status_code == 303
    assert tuple(saved(accounts)[0]) == (123, 'Portal 2', 'co1rs4')
    assert save(alice).status_code == 303 and len(saved(accounts)) == 1
    assert len(saved(accounts, BOB)) == 0
    assert 'Wishlisted' in alice.get('/games/123/portal-2', follow_redirects=True).get_data(as_text=True)
    with accounts.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM profile_achievements').fetchone()[0] == 0
        assert db.execute('SELECT share_wishlist FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0]
        assert db.execute("SELECT relrowsecurity FROM pg_class WHERE oid = 'wishlist_games'::regclass").fetchone()[0]
        assert db.execute("SELECT COUNT(*) FROM information_schema.table_privileges WHERE table_schema = current_schema() AND table_name = 'wishlist_games' AND grantee = 'PUBLIC'").fetchone()[0] == 0


def test_csrf_and_session_ownership_apply_to_every_mutation(accounts):
    fake_catalog(accounts)
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    save(alice)
    assert alice.post('/wishlist/games/123/remove').status_code == 400
    assert submit(bob, '/wishlist/games/123/remove', {'owner_id': ALICE}, source='/library/wishlist').status_code == 303
    assert len(saved(accounts)) == 1
    assert submit(alice, '/wishlist/games/123/remove', {}, source='/library/wishlist').status_code == 303
    assert not saved(accounts)
    assert accounts.test_client().get('/library/wishlist').status_code == 302
    with accounts.app_context():
        get_db().execute('UPDATE account_sessions SET recovery = 1 WHERE user_id = ?', (BOB,))
    assert bob.get('/library/wishlist').location.endswith('/account/password')


def test_transfer_uses_full_add_flow_and_keeps_wish_on_validation_or_save_failure(accounts, monkeypatch):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    save(alice)
    add = {'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Backlog'}
    assert 'Saving this game moves it to your library.' in alice.get('/library/add?igdb_id=123').get_data(as_text=True)
    assert alice.get('/explore/games/123/add').status_code == 302
    assert saved(accounts)
    assert submit(alice, '/library/add', {**add, 'rating': '11'}, source='/library/add?igdb_id=123').status_code == 200
    assert saved(accounts)
    def fail_award():
        raise psycopg.DatabaseError('Simulated local rollback')
    with monkeypatch.context() as patch:
        patch.setattr('app.routes.award_current', fail_award)
        assert submit(alice, '/library/add', add, source='/library/add?igdb_id=123').status_code == 200
    assert saved(accounts)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0
    assert submit(alice, '/library/add', add, source='/library/add?igdb_id=123').status_code == 302
    assert not saved(accounts)
    assert save(alice).status_code == 303 and not saved(accounts)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 1


def test_concurrent_library_and_wishlist_saves_leave_only_the_owned_game(accounts):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    fake_catalog(accounts)
    adding, wishing = sign_in(accounts, 'alice'), sign_in(accounts, 'alice')
    tokens = []
    for client, path in ((adding, '/library/add?igdb_id=123'), (wishing, '/library/wishlist')):
        parser = CSRFTokenParser()
        parser.feed(client.get(path, follow_redirects=True).get_data(as_text=True))
        tokens.append(parser.token)
    barrier = Barrier(2)
    def add_game():
        barrier.wait(timeout=10)
        return adding.post('/library/add', data={'csrf_token': tokens[0], 'title': 'Portal 2', 'igdb_id': '123', 'platform': 'PC', 'status': 'Backlog'}).status_code
    def add_wish():
        barrier.wait(timeout=10)
        return wishing.post('/wishlist/games/123/add', data={'csrf_token': tokens[1]}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        owned, wished = pool.submit(add_game), pool.submit(add_wish)
        assert owned.result(timeout=20) == 302
        assert wished.result(timeout=20) == 303
    assert not saved(accounts)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games WHERE owner_id = ?', (ALICE,)).fetchone()[0] == 1


def test_backup_import_moves_wishes_without_publishing_library_notes(accounts, backup_entry):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    save(alice)
    result = import_file(alice, encoded([backup_entry]))
    assert result.status_code == 200 and b'Imported 1 entries' in result.data
    assert not saved(accounts)
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM public_game_reviews').fetchone()[0] == 0


def test_public_wishlist_respects_private_option_and_profile_visibility(accounts):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    save(alice)
    visitor = accounts.test_client()
    publish(alice, share='no')
    path = '/players/alice_player/wishlist'
    assert visitor.get(path).status_code == 404
    assert 'profile-wishlist-link' not in visitor.get('/players/alice_player').get_data(as_text=True)
    publish(alice)
    response = visitor.get(path)
    html = response.get_data(as_text=True)
    assert response.status_code == 200 and 'Portal 2' in html
    assert 'View game' in html and 'Add to library' not in html and 'wishlist-remove' not in html
    for private in (ALICE, 'alice@example.test', 'alice-access', 'Privacy settings', 'Remove Portal 2'):
        assert private not in html
    assert 'no-store' in response.headers['Cache-Control']
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert 'profile-wishlist-link' in visitor.get('/players/alice_player').get_data(as_text=True)
    assert alice.get(path).status_code == 302
    submit(alice, '/account/profile/sharing', {'username': 'alice_player', 'share_wishlist': 'yes'})
    assert visitor.get(path).status_code == 404


def test_editor_can_toggle_sharing_and_legacy_forms_preserve_wishlist_privacy(accounts):
    alice = sign_in(accounts, 'alice')
    publish(alice)
    assert submit(alice, '/settings/profile', {'display_name': 'Alice'}).status_code == 303
    with accounts.app_context():
        assert get_db().execute('SELECT share_wishlist FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0]
    assert submit(alice, '/settings/profile', {'display_name': 'Alice', 'wishlist_controls': 'yes'}).status_code == 303
    with accounts.app_context():
        assert not get_db().execute('SELECT share_wishlist FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0]


def test_public_default_and_explicit_private_checkbox_persist_without_publishing_private_profiles(accounts):
    alice = sign_in(accounts, 'alice')
    submit(alice, '/account/profile/sharing', {'username': 'alice_player', 'is_public': 'yes'})
    visitor = accounts.test_client()
    assert visitor.get('/players/alice_player/wishlist').status_code == 200
    html = alice.get('/settings/profile', follow_redirects=True).get_data(as_text=True)
    import re
    checkbox = re.search(r'<input[^>]*name="private_wishlist"[^>]*>', html).group(0)
    assert 'checked' not in checkbox
    assert submit(alice, '/settings/profile', {'display_name': 'Alice', 'wishlist_privacy_controls': 'yes', 'private_wishlist': 'yes'}).status_code == 303
    assert visitor.get('/players/alice_player/wishlist').status_code == 404
    assert submit(alice, '/settings/profile', {'display_name': 'Alice'}).status_code == 303
    assert 'Applied 0' in accounts.test_cli_runner().invoke(args=['migrate-db']).output
    assert visitor.get('/players/alice_player/wishlist').status_code == 404
    assert submit(alice, '/settings/profile', {'display_name': 'Alice', 'wishlist_privacy_controls': 'yes'}).status_code == 303
    assert visitor.get('/players/alice_player/wishlist').status_code == 200
    submit(alice, '/account/profile/sharing', {'username': 'alice_player'})
    assert visitor.get('/players/alice_player/wishlist').status_code == 404
    with accounts.app_context():
        assert tuple(get_db().execute('SELECT is_public,share_wishlist FROM profiles WHERE id = ?', (ALICE,)).fetchone()) == (False, True)


def test_sign_in_returns_to_selected_game_without_silently_saving_a_wish(accounts):
    fake_catalog(accounts)
    sign_in(accounts, 'alice')
    visitor = accounts.test_client()
    response = visitor.get('/wishlist/games/123/continue?next=https://external.example')
    assert response.location.endswith('/account/login')
    result = submit(visitor, '/account/login', {'email': 'alice@example.test', 'password': 'test-password'})
    assert result.location.endswith('/games/123/game#game-actions')
    assert not saved(accounts)
    assert save(visitor).status_code == 303 and len(saved(accounts)) == 1


def test_setup_keeps_the_wishlist_intent_without_publishing_anything(accounts):
    fake_catalog(accounts)
    visitor = accounts.test_client()
    visitor.get('/wishlist/games/123/continue')
    result = submit(visitor, '/account/login', {'email': 'alice@example.test', 'password': 'test-password'})
    assert result.location.endswith('/settings/profile')
    assert submit(visitor, '/settings/profile', {'display_name': 'Alice', 'username': 'new_player'}).status_code == 303
    html = visitor.get('/players/new_player').get_data(as_text=True)
    assert '/games/123/game#game-actions' in html
    assert not saved(accounts)


def test_canonical_account_and_old_public_aliases_cannot_bypass_privacy(accounts):
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    publish(alice)
    publish(bob, 'bob_player')
    assert alice.get('/library/wishlist').status_code == 200
    assert alice.get('/account/alice_player/wishlist').location == '/library/wishlist'
    assert bob.get('/account/alice_player/wishlist').status_code == 404
    with accounts.app_context():
        get_db().execute('UPDATE profiles SET username_changed_at = NULL WHERE id = ?', (ALICE,))
    publish(alice, 'renamed_player')
    visitor = accounts.test_client()
    assert visitor.get('/players/alice_player/wishlist').location.endswith('/players/renamed_player/wishlist')
    publish(alice, 'renamed_player', 'no')
    assert visitor.get('/players/alice_player/wishlist').status_code == 404


def test_saved_titles_survive_provider_outages_and_can_still_be_removed(accounts):
    catalog = fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    save(alice)
    catalog.get_game.side_effect = CatalogError('Offline')
    assert 'Portal 2' in alice.get('/library/wishlist', follow_redirects=True).get_data(as_text=True)
    assert save(alice).status_code == 303 and len(saved(accounts)) == 1
    assert submit(alice, '/wishlist/games/123/remove', {}, source='/library/wishlist').status_code == 303
    assert not saved(accounts)


@pytest.mark.parametrize('catalog_id', [0, 999, 2**63])
def test_invalid_or_unknown_catalog_id_never_creates_a_wish(accounts, catalog_id):
    fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    assert save(alice, catalog_id).status_code == 404
    assert not saved(accounts)


def test_bounded_pagination_search_escaping_and_capacity(accounts):
    catalog = fake_catalog(accounts)
    alice = sign_in(accounts, 'alice')
    with accounts.app_context():
        db = get_db()
        for index in range(25):
            db.execute('INSERT INTO wishlist_games (owner_id,catalog_id,title) VALUES (?,?,?)', (ALICE, 1000 + index, '<b>Wish</b> ' + str(index)))
    html = alice.get('/library/wishlist', follow_redirects=True).get_data(as_text=True)
    assert html.count('class="wishlist-card"') == 24
    assert '&lt;b&gt;Wish&lt;/b&gt;' in html and '<b>Wish</b>' not in html
    assert alice.get('/library/wishlist?page=2', follow_redirects=True).get_data(as_text=True).count('class="wishlist-card"') == 1
    assert alice.get('/library/wishlist?page=3', follow_redirects=True).status_code == 404
    assert b'No matching wishes.' in alice.get('/library/wishlist?q=%25', follow_redirects=True).data
    assert alice.get('/library/wishlist?q=' + 'x' * 201, follow_redirects=True).status_code == 400
    assert alice.get('/library/wishlist?page=invalid', follow_redirects=True).status_code == 400
    accounts.config['PUBLIC_CATALOG_REQUEST_LIMIT'] = 0
    assert save(alice).status_code == 303 and len(saved(accounts)) == 25
    accounts.config['PUBLIC_CATALOG_REQUEST_LIMIT'] = 60
    with accounts.app_context():
        db = get_db()
        for index in range(25, 500):
            db.execute('INSERT INTO wishlist_games (owner_id,catalog_id,title) VALUES (?,?,?)', (ALICE, 1000 + index, 'Wish ' + str(index)))
    assert save(alice).status_code == 303 and len(saved(accounts)) == 500


def test_migration_keeps_profile_visibility_and_libraries_with_public_wishlist_defaults(postgres_config, tmp_path, monkeypatch):
    if not postgres_config:
        pytest.skip('Requires disposable PostgreSQL schemas')
    original = migrations.MIGRATIONS
    for path in sorted(original.glob('[0-9]*.sql'))[:14]:
        (tmp_path / path.name).write_bytes(path.read_bytes())
    application = create_app({'TESTING': True, 'SECRET_KEY': 'wishlist-migration-only', **postgres_config})
    with monkeypatch.context() as patch:
        patch.setattr(migrations, 'MIGRATIONS', tmp_path)
        assert application.test_cli_runner().invoke(args=['migrate-db']).exit_code == 0
        with application.app_context():
            db = get_db()
            db.execute("INSERT INTO profiles (id,display_name) VALUES (?,'Existing')", (ALICE,))
            db.execute("INSERT INTO profile_usernames (username,owner_id) VALUES ('existing_player',?)", (ALICE,))
            db.execute("UPDATE profiles SET username='existing_player',is_public=TRUE,share_statistics=FALSE WHERE id = ?", (ALICE,))
            db.execute("INSERT INTO games (owner_id,title,platform) VALUES (?,'Private game','PC')", (ALICE,))
    result = application.test_cli_runner().invoke(args=['migrate-db'])
    expected = len(list(original.glob('[0-9]*.sql'))) - 14
    assert result.exit_code == 0 and f'Applied {expected}' in result.output
    with application.app_context():
        db = get_db()
        assert tuple(db.execute('SELECT is_public,share_statistics,share_wishlist FROM profiles WHERE id = ?', (ALICE,)).fetchone()) == (True, False, True)
        assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM wishlist_games').fetchone()[0] == 0
    assert 'Applied 0' in application.test_cli_runner().invoke(args=['migrate-db']).output
