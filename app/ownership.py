"""Explicit server-side ownership for every collection query.

PostgreSQL owner connections bypass RLS. These predicates are the application's
authorization boundary; the public Supabase Data API has no table policies.
SQLite remains an offline, single-user mode.
"""

from uuid import UUID

from flask import current_app, g, has_request_context


def owner_id():
    if not current_app.config.get("AUTH_ENABLED"):
        return None
    user = getattr(g, "user", None) if has_request_context() else None
    if not user:
        raise RuntimeError("A verified user is required for collection access.")
    return str(UUID(user["id"]))


def owned(alias=""):
    """Return trusted SQL only; never interpolate an unvalidated identifier."""
    if alias not in ("", "g", "l"):
        raise ValueError("Invalid ownership alias.")
    if not current_app.config.get("DATABASE_URL"):
        return "1 = 1"
    column = f"{alias}.owner_id" if alias else "owner_id"
    user_id = owner_id()
    # UUID normalizes the verified identity before it becomes an SQL literal.
    return f"{column} = '{user_id}'" if user_id else f"{column} IS NULL"


def member_owned():
    return f"list_id IN (SELECT id FROM game_lists WHERE {owned()}) AND game_id IN (SELECT id FROM games WHERE {owned()})"


def insert_owned(db, table, fields, values):
    if table not in ("games", "game_lists"):
        raise ValueError("Invalid collection table.")
    fields, values = list(fields), list(values)
    if current_app.config.get("DATABASE_URL"):
        fields.append("owner_id")
        values.append(owner_id())
    return db.execute(
        f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) RETURNING id",
        values,
    )


def insert_members(db, pairs):
    if current_app.config.get("DATABASE_URL"):
        db.executemany("INSERT INTO game_list_members (list_id, game_id, owner_id) VALUES (?, ?, ?) ON CONFLICT (list_id, game_id) DO NOTHING",
                       [(list_id, game_id, owner_id()) for list_id, game_id in pairs])
    else:
        db.executemany("INSERT INTO game_list_members (list_id, game_id) VALUES (?, ?) ON CONFLICT (list_id, game_id) DO NOTHING", pairs)
