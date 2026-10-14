import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        # Additive migration: preserve existing collections and legacy entries.
        columns = g.db.execute("PRAGMA table_info(games)").fetchall()
        if columns and "igdb_id" not in {column["name"] for column in columns}:
            g.db.execute("BEGIN IMMEDIATE")
            columns = g.db.execute("PRAGMA table_info(games)").fetchall()
            if "igdb_id" not in {column["name"] for column in columns}:
                g.db.execute("ALTER TABLE games ADD COLUMN igdb_id INTEGER")
            g.db.commit()

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()

@click.command("init-db")
@with_appcontext
def init_db_command():
    db = get_db()

    with current_app.open_resource("schema.sql") as schema_file:
        db.executescript(schema_file.read().decode("utf-8"))

    click.echo("Database initialized.")
