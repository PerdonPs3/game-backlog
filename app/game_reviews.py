"""Explicit public reviews, separate from private collection notes."""

import click
from flask import Blueprint, abort, current_app, flash, g, redirect, request, url_for
from flask.cli import with_appcontext

from app.db import get_db


reviews = Blueprint('reviews', __name__)
PAGE_SIZE = 10
REPORT_REASONS = ('spam', 'abuse', 'spoilers', 'other')
VISIBLE = 'p.is_public AND p.username IS NOT NULL AND NOT r.moderation_hidden'


def require_reviewer():
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    if not g.user:
        return redirect(url_for('auth.login'))
    if g.account_session['recovery']:
        return redirect(url_for('auth.password'))
    if not g.profile or not g.profile['display_name'].strip() or not g.profile['username']:
        return redirect(url_for('auth.profile'))


def review_context(catalog_id):
    if not current_app.config.get('AUTH_ENABLED'):
        return {'reviews_enabled': False}
    db = get_db()
    owner = g.user['id'] if g.user else None
    normal = bool(owner and not g.account_session['recovery'] and g.profile and g.profile['username'])
    public = db.execute('SELECT is_public FROM profiles WHERE id = ?', (owner,)).fetchone() if normal else None
    own = db.execute('SELECT rating, body, has_spoilers, moderation_hidden FROM public_game_reviews '
                     'WHERE catalog_id = ? AND owner_id = ?', (catalog_id, owner)).fetchone() if normal else None
    try:
        page = int(request.args.get('reviews_page', '1'))
    except ValueError:
        abort(400)
    if not 1 <= page <= 10000:
        abort(400)
    # No private collection data or account identifiers enter the public projection.
    visible = VISIBLE + (' AND NOT EXISTS (SELECT 1 FROM public_review_reports f '
                         'WHERE f.review_id = r.id AND f.reporter_id = ?)' if normal else '')
    params = (catalog_id, owner) if normal else (catalog_id,)
    summary = db.execute('SELECT COUNT(*), AVG(r.rating) FROM public_game_reviews r '
                         'JOIN profiles p ON p.id = r.owner_id WHERE r.catalog_id = ? AND ' + visible, params).fetchone()
    rows = db.execute('SELECT r.id, r.rating, r.body, r.has_spoilers, r.updated_at, '
                      'p.display_name, p.username, r.owner_id = ? AS is_own '
                      'FROM public_game_reviews r JOIN profiles p ON p.id = r.owner_id '
                      'WHERE r.catalog_id = ? AND ' + visible + ' ORDER BY r.updated_at DESC, r.id DESC LIMIT ? OFFSET ?',
                      (owner, *params, PAGE_SIZE, (page - 1) * PAGE_SIZE)).fetchall()
    return {'reviews_enabled': True, 'community_reviews': rows, 'review_count': summary[0],
            'review_average': summary[1], 'reviews_page': page, 'reviews_has_next': page * PAGE_SIZE < summary[0],
            'own_review': own, 'review_can_publish': bool(public and public[0]), 'review_normal_session': normal}


def begin_review_write(db, *, publishing=False):
    """Serialize writes per account and enforce a shared, persistent hourly budget."""
    db.execute('BEGIN')
    profile = db.execute('SELECT is_public FROM profiles WHERE id = ? FOR UPDATE', (g.user['id'],)).fetchone()
    if publishing and not profile['is_public']:
        db.rollback()
        return 'Make your profile public before publishing a review.'
    db.execute("DELETE FROM public_review_events WHERE created_at < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '1 hour'")
    count = db.execute('SELECT COUNT(*) FROM public_review_events WHERE owner_id = ?', (g.user['id'],)).fetchone()[0]
    if count >= 30:
        db.rollback()
        return 'You have made too many review changes. Please try again in an hour.'
    db.execute('INSERT INTO public_review_events (owner_id) VALUES (?)', (g.user['id'],))
    return None


def publish_review(catalog_id):
    """Called only after the catalog has verified the requested game exists."""
    body = request.form.get('body', '').strip()
    try:
        rating = int(request.form.get('rating', ''))
    except ValueError:
        rating = 0
    if not 1 <= rating <= 10:
        return 'Choose a rating from the five-star scale.'
    if not 1 <= len(body) <= 2000 or '\x00' in body:
        return 'Write a review with 1 to 2,000 characters.'
    db = get_db()
    try:
        error = begin_review_write(db, publishing=True)
        if error:
            return error
        db.execute('INSERT INTO public_game_reviews (catalog_id, owner_id, rating, body, has_spoilers) '
                   'VALUES (?, ?, ?, ?, ?) ON CONFLICT (catalog_id, owner_id) DO UPDATE '
                   "SET rating = EXCLUDED.rating, body = EXCLUDED.body, has_spoilers = EXCLUDED.has_spoilers, updated_at = (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')",
                   (catalog_id, g.user['id'], rating, body, request.form.get('has_spoilers') == 'yes'))
        db.commit()
    except Exception:
        db.rollback()
        raise


def review_redirect(catalog_id):
    return redirect(url_for('explore.game', catalog_id=catalog_id, _anchor='community-reviews'), code=303)


@reviews.post('/explore/games/<int:catalog_id>/reviews/delete')
def delete(catalog_id):
    if not 0 < catalog_id < 2**63:
        abort(404)
    guard = require_reviewer()
    if guard:
        return guard
    # Removing your public content remains possible even after reaching the write budget.
    get_db().execute('DELETE FROM public_game_reviews WHERE catalog_id = ? AND owner_id = ?',
                     (catalog_id, g.user['id']))
    flash('Your public review was deleted. Your private notes are unchanged.', 'review_saved')
    return review_redirect(catalog_id)


@reviews.post('/explore/games/<int:catalog_id>/reviews/<int:review_id>/report')
def report(catalog_id, review_id):
    if not 0 < catalog_id < 2**63 or not 0 < review_id < 2**63:
        abort(404)
    guard = require_reviewer()
    if guard:
        return guard
    if request.form.get('reason') not in REPORT_REASONS:
        abort(400)
    db = get_db()
    try:
        error = begin_review_write(db)
        if error:
            flash(error, 'review_error')
            return review_redirect(catalog_id)
        row = db.execute('SELECT r.id FROM public_game_reviews r JOIN profiles p ON p.id = r.owner_id '
                         'WHERE r.id = ? AND r.catalog_id = ? AND r.owner_id <> ? AND ' + VISIBLE + ' FOR UPDATE OF r',
                         (review_id, catalog_id, g.user['id'])).fetchone()
        if not row:
            db.rollback()
            abort(404)
        db.execute('INSERT INTO public_review_reports (review_id, reporter_id, reason) VALUES (?, ?, ?) '
                   'ON CONFLICT (review_id, reporter_id) DO NOTHING',
                   (review_id, g.user['id'], request.form['reason']))
        db.commit()
    except Exception:
        db.rollback()
        raise
    flash('Report recorded. This review is now hidden for you.', 'review_saved')
    return review_redirect(catalog_id)


@click.command('moderate-review')
@click.option('--review-id', type=click.IntRange(min=1), required=True)
@click.option('--hide/--restore', default=True)
@click.option('--apply', is_flag=True, help='Save the moderation decision. Default: inspect only.')
@with_appcontext
def moderate_review(review_id, hide, apply):
    """Inspect reported content and hide or restore it using server operator access."""
    if not current_app.config.get('DATABASE_URL'):
        raise click.ClickException('This command requires PostgreSQL.')
    db = get_db()
    row = db.execute('SELECT catalog_id, body, moderation_hidden FROM public_game_reviews WHERE id = ?', (review_id,)).fetchone()
    if not row:
        raise click.ClickException('Review not found.')
    count = db.execute('SELECT COUNT(*) FROM public_review_reports WHERE review_id = ?', (review_id,)).fetchone()[0]
    click.echo(f'Game {row["catalog_id"]} · {count} reports · hidden: {row["moderation_hidden"]}')
    click.echo(row['body'])
    if apply:
        db.execute('UPDATE public_game_reviews SET moderation_hidden = ? WHERE id = ?', (hide, review_id))
    click.echo('Saved.' if apply else 'Preview only; add --apply to save.')


@click.command('review-reports')
@with_appcontext
def review_reports():
    """List up to 50 reported reviews for a server operator, without exposing reporters."""
    if not current_app.config.get('DATABASE_URL'):
        raise click.ClickException('This command requires PostgreSQL.')
    rows = get_db().execute('SELECT r.id, r.catalog_id, r.moderation_hidden, COUNT(*) AS reports '
                            'FROM public_game_reviews r JOIN public_review_reports f ON f.review_id = r.id '
                            'GROUP BY r.id ORDER BY MAX(f.created_at) DESC, r.id DESC LIMIT 50').fetchall()
    for row in rows:
        click.echo(f'Review {row["id"]} · game {row["catalog_id"]} · {row["reports"]} reports · hidden: {row["moderation_hidden"]}')
    if not rows:
        click.echo('No reported reviews.')


def init_app(app):
    app.register_blueprint(reviews)
    app.cli.add_command(moderate_review)
    app.cli.add_command(review_reports)

    @app.after_request
    def review_headers(response):
        if request.blueprint == 'reviews':
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['Referrer-Policy'] = 'same-origin'
        return response
