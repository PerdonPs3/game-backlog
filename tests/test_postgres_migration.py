"""Run with --postgres-url against a dedicated test database, never production."""

import hashlib
import sqlite3

import pytest

from app import create_app
from app.db import get_db
from app.migrations import read_sqlite_collection
import app.migrations as migrations


@pytest.fixture
def postgres_app(app):
    if not app.config.get("DATABASE_URL"):
        pytest.skip("Requires --postgres-url or TEST_DATABASE_URL")
    return app


@pytest.fixture
def sqlite_source(tmp_path):
    path = tmp_path / "source.sqlite"
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    assert application.test_cli_runner().invoke(args=["init-db"]).exit_code == 0
    with application.app_context():
        db = get_db()
        db.execute("INSERT INTO games (id, title, platform, status, rating, review, igdb_id, cover_image_id, started_on, completed_on, created_at, is_favorite, is_goty) "
                   "VALUES (42, 'A game', 'PC', 'Completed', 9, 'Original review', 123, 'co_test', '2026-01-02', '2026-02-03', '2026-01-01 12:30:00', 1, 1)")
        db.execute("INSERT INTO game_lists (id, name, name_key, created_at) VALUES (17, 'Favorites', 'favorites', '2026-01-01 13:00:00')")
        db.execute("INSERT INTO game_list_members VALUES (17, 42)")
        db.commit()
    return path


def test_sqlite_dry_run_never_opens_target_or_changes_source(sqlite_source):
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE_URL": "postgresql://unreachable.invalid/test"})
    before = hashlib.sha256(sqlite_source.read_bytes()).digest()
    result = application.test_cli_runner().invoke(args=["migrate-sqlite", "--source", str(sqlite_source)])
    assert result.exit_code == 0, result.output
    assert "Validated 1 games, 1 lists, and 1 memberships" in result.output
    assert hashlib.sha256(sqlite_source.read_bytes()).digest() == before


def test_sqlite_validation_rejects_bad_dates_without_touching_source(sqlite_source):
    with sqlite3.connect(sqlite_source) as db:
        db.execute("UPDATE games SET started_on = '2026-02-30', completed_on = NULL")
    before = sqlite_source.read_bytes()
    with pytest.raises(ValueError):
        read_sqlite_collection(sqlite_source)
    assert sqlite_source.read_bytes() == before


def test_migrations_are_repeatable_and_health_check_is_read_only(postgres_app):
    runner = postgres_app.test_cli_runner()
    result = runner.invoke(args=["migrate-db"])
    assert result.exit_code == 0 and "Applied 0" in result.output
    assert runner.invoke(args=["check-db"]).exit_code == 0
    assert runner.invoke(args=["init-db"]).exit_code != 0
    with postgres_app.app_context():
        db = get_db()
        assert len(db.execute("SELECT * FROM schema_migrations").fetchall()) == len(list(migrations.MIGRATIONS.glob('[0-9]*.sql')))
        assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
        assert all(row[0] for row in db.execute("SELECT relrowsecurity FROM pg_class WHERE relnamespace = current_schema()::regnamespace AND relname IN ('games', 'game_lists', 'game_list_members')"))


def test_failed_schema_migration_rolls_back_ddl_and_version(postgres_app, tmp_path, monkeypatch):
    original = migrations.MIGRATIONS
    (tmp_path / "001_initial.sql").write_text((original / "001_initial.sql").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "002_private_accounts.sql").write_bytes((original / "002_private_accounts.sql").read_bytes())
    (tmp_path / "003_profile_photos.sql").write_bytes((original / "003_profile_photos.sql").read_bytes())
    (tmp_path / "004_profile_showcase.sql").write_bytes((original / "004_profile_showcase.sql").read_bytes())
    (tmp_path / "005_public_profiles.sql").write_bytes((original / "005_public_profiles.sql").read_bytes())
    (tmp_path / "006_username_history.sql").write_bytes((original / "006_username_history.sql").read_bytes())
    (tmp_path / "007_profile_country.sql").write_bytes((original / "007_profile_country.sql").read_bytes())
    (tmp_path / "008_country_profile_visibility.sql").write_bytes((original / "008_country_profile_visibility.sql").read_bytes())
    (tmp_path / "009_broken.sql").write_text("CREATE TABLE rollback_probe (id INTEGER); SELECT missing_column FROM games;", encoding="utf-8")
    monkeypatch.setattr(migrations, "MIGRATIONS", tmp_path)
    result = postgres_app.test_cli_runner().invoke(args=["migrate-db"])
    assert result.exit_code != 0 and "rolled back" in result.output
    with postgres_app.app_context():
        db = get_db()
        assert db.execute("SELECT to_regclass('rollback_probe')").fetchone()[0] is None
        assert len(db.execute("SELECT * FROM schema_migrations").fetchall()) == 8


def test_changed_applied_migration_is_rejected(postgres_app, tmp_path, monkeypatch):
    (tmp_path / "001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "002_private_accounts.sql").write_bytes((migrations.MIGRATIONS / "002_private_accounts.sql").read_bytes())
    (tmp_path / "003_profile_photos.sql").write_bytes((migrations.MIGRATIONS / "003_profile_photos.sql").read_bytes())
    (tmp_path / "004_profile_showcase.sql").write_bytes((migrations.MIGRATIONS / "004_profile_showcase.sql").read_bytes())
    (tmp_path / "005_public_profiles.sql").write_bytes((migrations.MIGRATIONS / "005_public_profiles.sql").read_bytes())
    (tmp_path / "006_username_history.sql").write_bytes((migrations.MIGRATIONS / "006_username_history.sql").read_bytes())
    (tmp_path / "007_profile_country.sql").write_bytes((migrations.MIGRATIONS / "007_profile_country.sql").read_bytes())
    (tmp_path / "008_country_profile_visibility.sql").write_bytes((migrations.MIGRATIONS / "008_country_profile_visibility.sql").read_bytes())
    monkeypatch.setattr(migrations, "MIGRATIONS", tmp_path)
    result = postgres_app.test_cli_runner().invoke(args=["migrate-db"])
    assert result.exit_code != 0 and "has changed" in result.output


def test_username_history_upgrade_preserves_existing_names_and_publication(postgres_config, tmp_path, monkeypatch):
    if not postgres_config:
        pytest.skip('Requires disposable PostgreSQL schemas')
    from app.public_profiles import save_sharing
    owner = '11111111-1111-4111-8111-111111111111'
    original = migrations.MIGRATIONS
    for path in sorted(original.glob('[0-9]*.sql'))[:5]:
        (tmp_path / path.name).write_bytes(path.read_bytes())
    application = create_app({'TESTING':True, 'SECRET_KEY':'migration-tests', **postgres_config})
    with monkeypatch.context() as patch:
        patch.setattr(migrations, 'MIGRATIONS', tmp_path)
        assert application.test_cli_runner().invoke(args=['migrate-db']).exit_code == 0
        with application.app_context():
            get_db().execute("INSERT INTO profiles (id,display_name,username,is_public) VALUES (?, 'Existing player', 'existing_name', TRUE)", (owner,))
    result = application.test_cli_runner().invoke(args=['migrate-db'])
    assert result.exit_code == 0 and 'Applied 3' in result.output
    with application.app_context():
        db = get_db()
        row = db.execute('SELECT username, username_changed_at, is_public, country_code FROM profiles WHERE id = ?', (owner,)).fetchone()
        assert row['username'] == 'existing_name' and row['username_changed_at'] is None and row['is_public']
        assert row['country_code'] is None
        assert str(db.execute("SELECT owner_id FROM profile_usernames WHERE username = 'existing_name'").fetchone()[0]) == owner
        # Old installations have no historical claim time: allow one change immediately.
        save_sharing(db, owner, {'username':'updated_name', 'is_public':'yes'})
        assert db.execute('SELECT username FROM profiles WHERE id = ?', (owner,)).fetchone()[0] == 'updated_name'
        assert db.execute('SELECT COUNT(*) FROM profile_usernames WHERE owner_id = ?', (owner,)).fetchone()[0] == 2


def test_transfer_preserves_fields_relationships_and_next_ids(postgres_app, sqlite_source):
    before = sqlite_source.read_bytes()
    runner = postgres_app.test_cli_runner()
    args = ["migrate-sqlite", "--source", str(sqlite_source), "--apply"]
    result = runner.invoke(args=args)
    assert result.exit_code == 0, result.output
    with postgres_app.app_context():
        db = get_db()
        source_games, source_lists, source_members = read_sqlite_collection(sqlite_source)
        assert [{key: row[key] for key in source_games[0]} for row in db.execute("SELECT * FROM games")] == source_games
        assert [{key: row[key] for key in source_lists[0]} for row in db.execute("SELECT * FROM game_lists")] == source_lists
        assert [tuple(row) for row in db.execute("SELECT list_id, game_id FROM game_list_members")] == source_members
        assert db.execute("SELECT owner_id FROM games").fetchone()[0] is None
        assert db.execute("INSERT INTO games (title, platform) VALUES ('Next', 'PC') RETURNING id").fetchone()[0] == 43
        assert db.execute("INSERT INTO game_lists (name, name_key) VALUES ('Next', 'next') RETURNING id").fetchone()[0] == 18
    assert runner.invoke(args=args).exit_code != 0
    assert sqlite_source.read_bytes() == before


def test_failed_transfer_leaves_no_partial_collection(postgres_app, sqlite_source):
    with sqlite3.connect(sqlite_source) as source:
        # SQLite permits NUL text but PostgreSQL does not. This fails during
        # insertion, after source validation, to exercise the target rollback.
        source.execute("INSERT INTO games (id, title, platform, review) VALUES (43, 'Broken', 'PC', ?)", ("Broken\0review",))
    result = postgres_app.test_cli_runner().invoke(args=["migrate-sqlite", "--source", str(sqlite_source), "--apply"])
    assert result.exit_code != 0
    with postgres_app.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM game_lists").fetchone()[0] == 0


def test_dry_run_rejects_dangling_source_memberships(sqlite_source):
    with sqlite3.connect(sqlite_source) as source:
        source.execute("INSERT INTO game_list_members VALUES (17, 999)")
    with pytest.raises(ValueError, match="missing games"):
        read_sqlite_collection(sqlite_source)


def test_regular_postgres_connection_does_not_create_schema(postgres_config):
    if not postgres_config:
        pytest.skip("Requires --postgres-url or TEST_DATABASE_URL")
    application = create_app({"TESTING": True, "SECRET_KEY": "test", **postgres_config})
    with application.app_context():
        assert get_db().execute("SELECT to_regclass('games')").fetchone()[0] is None
