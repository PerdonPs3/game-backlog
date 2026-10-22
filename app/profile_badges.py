"""Server-assigned cosmetic badges; these never grant application permissions."""

import click
from flask import current_app
from flask.cli import with_appcontext

from app.db import get_db


@click.command('set-admin-badge')
@click.option('--username', required=True, help='Current username of the verified account.')
@click.option('--remove', is_flag=True, help='Remove the cosmetic badge instead of assigning it.')
@click.option('--apply', is_flag=True, help='Save the assignment. Default: inspect the target only.')
@with_appcontext
def set_admin_badge(username, remove, apply):
    """Assign a cosmetic Creator badge to the account behind a current username."""
    if not current_app.config.get('DATABASE_URL'):
        raise click.ClickException('This command requires PostgreSQL.')
    db = get_db()
    db.execute('BEGIN')
    try:
        profile = db.execute('SELECT id, username FROM profiles WHERE username = ? FOR UPDATE', (username.strip().lower(),)).fetchone()
        if not profile:
            raise click.ClickException('No account has that current username. No changes were made.')
        if apply:
            db.execute('UPDATE profiles SET admin_badge = ? WHERE id = ?', (not remove, profile['id']))
            db.commit()
        else:
            db.rollback()
        action = 'Remove' if remove else 'Assign'
        click.echo(f"{action} Creator badge for @{profile['username']}: {'saved' if apply else 'preview only; add --apply to save'}.")
    except Exception:
        db.rollback()
        raise
