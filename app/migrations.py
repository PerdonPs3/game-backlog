"""Explicit PostgreSQL schema upgrades and read-only SQLite collection transfer."""

import hashlib
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

import click
from flask import current_app
from flask.cli import with_appcontext

from app.backups import BACKUP_FIELDS, _validate_entry
from app.db import DATABASE_ERRORS, begin_write, get_db
from app.game_lists import MAX_LISTS, clean_list_name


MIGRATIONS = Path(__file__).with_name("migrations")


def migrate_postgres(db):
    """Apply immutable, ordered SQL files atomically under a transaction lock."""
    db.execute("BEGIN")
    try:
        db.execute("SELECT pg_advisory_xact_lock(719245301)")
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, checksum TEXT NOT NULL)")
        db.execute("ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY")
        db.execute("REVOKE ALL ON schema_migrations FROM PUBLIC")
        applied = {row["version"]: row["checksum"] for row in db.execute("SELECT * FROM schema_migrations")}
        files = sorted(MIGRATIONS.glob("[0-9]*.sql"))
        if applied.keys() - {path.stem for path in files}:
            raise ValueError("The database has migrations newer than this application.")
        count = 0
        for path in files:
            source = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(source.replace("\r\n", "\n").encode()).hexdigest()
            if path.stem in applied:
                if applied[path.stem] != checksum:
                    raise ValueError("An applied migration has changed. Restore the original file.")
                continue
            for statement in source.split(";"):
                if statement.strip():
                    db.execute(statement)
            db.execute("INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)", (path.stem, checksum))
            count += 1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise


def require_postgres():
    if not current_app.config.get("DATABASE_URL"):
        raise click.ClickException("Set DATABASE_URL to use a PostgreSQL database.")
    return get_db()


@click.command("migrate-db")
@with_appcontext
def migrate_db_command():
    """Apply versioned PostgreSQL migrations without replacing existing data."""
    try:
        count = migrate_postgres(require_postgres())
    except DATABASE_ERRORS:
        raise click.ClickException("PostgreSQL migration failed and was rolled back. Check connectivity, permissions, and schema conflicts.") from None
    except ValueError as error:
        raise click.ClickException(str(error)) from None
    click.echo(f"PostgreSQL ready. Applied {count} migration(s).")


@click.command("check-db")
@with_appcontext
def check_db_command():
    """Check connectivity and schema without changing collection data."""
    try:
        db = require_postgres()
        applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations")}
        if applied != {path.stem for path in MIGRATIONS.glob("[0-9]*.sql")}:
            raise click.ClickException("Run migrate-db with this application version before serving requests.")
        for table in ("games", "game_lists", "game_list_members"):
            db.execute(f"SELECT 1 FROM {table} LIMIT 0")
    except DATABASE_ERRORS:
        raise click.ClickException("Database check failed. Check DATABASE_URL, network access, and migrate-db status.") from None
    click.echo("PostgreSQL connection and schema check successful.")


def read_sqlite_collection(path):
    """Read an initialized SQLite database in a consistent, read-only snapshot."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        source.execute("BEGIN")
        games = [dict(row) for row in source.execute("SELECT * FROM games ORDER BY id")]
        lists = [dict(row) for row in source.execute("SELECT * FROM game_lists ORDER BY id")]
        members = [tuple(row) for row in source.execute("SELECT list_id, game_id FROM game_list_members ORDER BY list_id, game_id")]
    # Reuse backup validation without its upload size limit; never silently fix
    # invalid source data or modify the source database to make it transferable.
    for game in games:
        if not set(BACKUP_FIELDS) <= game.keys():
            raise ValueError("Initialize the SQLite database with the current SQLite app before transferring it.")
        _validate_entry(game)
    if len(lists) > MAX_LISTS:
        raise ValueError("The source exceeds the supported list limit.")
    for item in lists:
        if clean_list_name(item["name"]).casefold() != item["name_key"]:
            raise ValueError("The source contains an invalid list name key.")
        datetime.fromisoformat(item["created_at"])
    game_ids = {game["id"] for game in games}
    list_ids = {item["id"] for item in lists}
    if any(list_id not in list_ids or game_id not in game_ids for list_id, game_id in members):
        raise ValueError("The source contains memberships referencing missing games or lists.")
    return games, lists, members


def transfer_sqlite(db, collection):
    games, lists, members = collection
    begin_write(db)
    try:
        if any(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is not None
               for table in ("games", "game_lists", "game_list_members")):
            raise ValueError("The target collection must be empty. Existing data was not changed.")
        fields = ("id", *BACKUP_FIELDS)
        for game in games:
            db.execute(f"INSERT INTO games ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                       [game[field] for field in fields])
        for item in lists:
            db.execute("INSERT INTO game_lists (id, name, name_key, created_at) VALUES (?, ?, ?, ?)",
                       [item[field] for field in ("id", "name", "name_key", "created_at")])
        db.executemany("INSERT INTO game_list_members (list_id, game_id) VALUES (?, ?)", members)
        for table in ("games", "game_lists"):
            # Transactional RESTART preserves identity sequences on rollback.
            next_id = db.execute(f"SELECT GREATEST(COALESCE(MAX(id), 0), 0) + 1 FROM {table}").fetchone()[0]
            db.execute(f"ALTER TABLE {table} ALTER COLUMN id RESTART WITH {int(next_id)}")
        db.commit()
    except Exception:
        db.rollback()
        raise


@click.command("migrate-sqlite")
@click.option("--source", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--apply", is_flag=True, help="Copy into an empty, migrated PostgreSQL collection. Default: validate source only.")
@with_appcontext
def migrate_sqlite_command(source, apply):
    """Validate a SQLite snapshot; copy it only with explicit --apply."""
    try:
        collection = read_sqlite_collection(source)
        if apply:
            transfer_sqlite(require_postgres(), collection)
    except DATABASE_ERRORS + (ValueError, KeyError, TypeError):
        raise click.ClickException("Transfer failed. Use a valid, initialized SQLite source and an empty, migrated PostgreSQL target. No partial transfer was committed.") from None
    games, lists, members = collection
    click.echo(f"{'Transferred' if apply else 'Validated'} {len(games)} games, {len(lists)} lists, and {len(members)} memberships.")
    if not apply:
        click.echo("Source opened read-only. No target connection or writes. Add --apply to transfer.")
