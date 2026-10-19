import sqlite3
import click
import psycopg
from flask import current_app, g
from flask.cli import with_appcontext

from app.postgres import PostgresConnection


INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
DATABASE_ERRORS = (sqlite3.DatabaseError, psycopg.DatabaseError)


def begin_write(db):
    if isinstance(db, PostgresConnection):
        db.execute("BEGIN")
        # Serialize collection writers just as SQLite BEGIN IMMEDIATE does.
        # This preserves duplicate checks and the list limit across requests.
        db.execute("LOCK TABLE games, game_lists, game_list_members IN SHARE ROW EXCLUSIVE MODE")
    else:
        db.execute("BEGIN IMMEDIATE")


def begin_snapshot(db):
    db.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY" if isinstance(db, PostgresConnection) else "BEGIN")


def title_contains_sql():
    return "strpos(lower(title), lower(?)) > 0" if current_app.config.get("DATABASE_URL") else "instr(lower(title), lower(?)) > 0"


def get_db():
    if "db" not in g and current_app.config.get("DATABASE_URL"):
        g.db = PostgresConnection(
            current_app.config["DATABASE_URL"],
            current_app.config.get("POSTGRES_TEST_SCHEMA") if current_app.testing else None,
        )
        return g.db
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        # Additive migration: preserve existing collections and legacy entries.
        columns = g.db.execute("PRAGMA table_info(games)").fetchall()
        additions = {
            "igdb_id": "ALTER TABLE games ADD COLUMN igdb_id INTEGER",
            "cover_image_id": "ALTER TABLE games ADD COLUMN cover_image_id TEXT",
            "started_on": "ALTER TABLE games ADD COLUMN started_on TEXT",
            "completed_on": "ALTER TABLE games ADD COLUMN completed_on TEXT",
            "is_favorite": "ALTER TABLE games ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1))",
            "is_goty": "ALTER TABLE games ADD COLUMN is_goty INTEGER NOT NULL DEFAULT 0 CHECK (is_goty IN (0, 1))",
        }
        schema = g.db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'games'").fetchone()
        needs_status_upgrade = schema is not None and "status" in {c["name"] for c in columns} and "'On hold'" not in schema["sql"]
        if columns and (additions.keys() - {column["name"] for column in columns} or needs_status_upgrade):
            g.db.execute("BEGIN IMMEDIATE")
            try:
                columns = g.db.execute("PRAGMA table_info(games)").fetchall()
                existing = {column["name"] for column in columns}
                for name, statement in additions.items():
                    if name not in existing:
                        g.db.execute(statement)
                schema = g.db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'games'").fetchone()
                if "status" in existing and "'On hold'" not in schema["sql"]:
                    # SQLite CHECK constraints require a new table. Keep the original
                    # as a safety snapshot; all changes commit or roll back together.
                    with current_app.open_resource("schema.sql") as schema_file:
                        table_sql = schema_file.read().decode("utf-8")
                    g.db.execute(table_sql.replace("IF NOT EXISTS games", "games_status_upgrade", 1))
                    names = [c["name"] for c in g.db.execute("PRAGMA table_info(games)")]
                    # Column identifiers originate only from SQLite's schema metadata.
                    quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
                    g.db.execute(f"INSERT INTO games_status_upgrade ({quoted}) SELECT {quoted} FROM games")
                    g.db.execute("ALTER TABLE games RENAME TO games_before_status_upgrade")
                    g.db.execute("ALTER TABLE games_status_upgrade RENAME TO games")
                g.db.commit()
            except Exception:
                g.db.rollback()
                g.db.close()
                g.pop("db", None)
                raise

        g.db.execute("PRAGMA foreign_keys = ON")
        if g.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'game_list_members'").fetchone() is None:
            g.db.execute("BEGIN IMMEDIATE")
            try:
                with current_app.open_resource("lists_schema.sql") as schema_file:
                    statements = schema_file.read().decode("utf-8").split(";")
                for statement in statements:
                    if statement.strip():
                        g.db.execute(statement)
                g.db.commit()
            except Exception:
                g.db.rollback()
                g.db.close()
                g.pop("db", None)
                raise

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()

@click.command("init-db")
@with_appcontext
def init_db_command():
    db = get_db()

    if isinstance(db, PostgresConnection):
        raise click.ClickException("PostgreSQL requires the migrate-db command; init-db is for SQLite only.")

    with current_app.open_resource("schema.sql") as schema_file:
        db.executescript(schema_file.read().decode("utf-8"))

    click.echo("Database initialized.")
