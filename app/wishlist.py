"""Separate catalog wishes, explicit publication, and atomic library transfers."""

import re

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app.achievements import normal_owner
from app.catalog import CatalogError, collection_cover_url, cover_image_id, get_catalog
from app.catalog_journey import remember_selection
from app.db import get_db


wishlist = Blueprint('wishlist', __name__)
PAGE_SIZE = 24
MAX_WISHES = 500


def save_privacy(db, owner, form):
    """Private is an explicit opt-out; old sharing forms remain compatible."""
    if form.get('wishlist_privacy_controls') == 'yes':
        db.execute('UPDATE profiles SET share_wishlist = ? WHERE id = ?',
                   (form.get('private_wishlist') != 'yes', owner))
    elif form.get('wishlist_controls') == 'yes' or 'share_wishlist' in form:
        db.execute('UPDATE profiles SET share_wishlist = ? WHERE id = ?',
                   (form.get('share_wishlist') == 'yes', owner))


@wishlist.before_request
def require_owner():
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    if request.endpoint in ('wishlist.public', 'wishlist.continue_selection'):
        return
    if not g.user:
        return redirect(url_for('auth.login'))
    if g.account_session['recovery']:
        return redirect(url_for('auth.password'))
    if not normal_owner():
        return redirect(url_for('auth.profile'))


def catalog_id_valid(catalog_id):
    if not 0 < catalog_id < 2**63:
        abort(404)


def wish_state(catalog_id):
    return bool(normal_owner() and get_db().execute(
        'SELECT 1 FROM wishlist_games WHERE owner_id = ? AND catalog_id = ?',
        (g.user['id'], catalog_id)).fetchone())


def consume_owned_wishes(db):
    """Remove wishes within the successful collection writer's transaction.

    Serialize with wishlist insertion so concurrent Add game and Wishlist saves
    cannot leave the same catalog title on both sides. No client transfer flag
    is required, so quick-add, full Add game, and backup imports all participate.
    """
    if normal_owner():
        owner = g.user['id']
        db.execute('SELECT id FROM profiles WHERE id = ? FOR UPDATE', (owner,))
        db.execute('DELETE FROM wishlist_games WHERE owner_id = ? AND catalog_id IN (SELECT igdb_id FROM games WHERE owner_id = ? AND igdb_id IS NOT NULL)', (owner, owner))


@wishlist.get('/wishlist/games/<int:catalog_id>/continue')
def continue_selection(catalog_id):
    catalog_id_valid(catalog_id)
    if normal_owner():
        return redirect(url_for('explore.game', catalog_id=catalog_id, _anchor='game-actions'))
    remember_selection(catalog_id, intent='wishlist')
    if g.user:
        return redirect(url_for('auth.password' if g.account_session['recovery'] else 'auth.profile'))
    return redirect(url_for('auth.login'))


@wishlist.post('/wishlist/games/<int:catalog_id>/add')
def add(catalog_id):
    catalog_id_valid(catalog_id)
    from app.public_catalog import public_request_allowed
    if not public_request_allowed():
        flash('The catalog is busy. Please try saving this game again shortly.', 'wishlist_error')
        return redirect(url_for('wishlist.index'), code=303)
    try:
        game = get_catalog().get_game(catalog_id)
    except CatalogError:
        flash('The catalog is temporarily unavailable. Your wishlist has not changed.', 'wishlist_error')
        return redirect(url_for('wishlist.index'), code=303)
    if game is None or game.get('id') != catalog_id:
        abort(404)
    title = game.get('name', '').strip()[:200]
    if not title:
        abort(404)
    db, owner = get_db(), g.user['id']
    db.execute('BEGIN')
    try:
        db.execute('SELECT id FROM profiles WHERE id = ? FOR UPDATE', (owner,))
        if db.execute('SELECT 1 FROM games WHERE owner_id = ? AND igdb_id = ?', (owner, catalog_id)).fetchone():
            message = 'This game is already in your library.'
        elif db.execute('SELECT 1 FROM wishlist_games WHERE owner_id = ? AND catalog_id = ?', (owner, catalog_id)).fetchone():
            message = 'Already on your wishlist.'
        elif db.execute('SELECT COUNT(*) FROM wishlist_games WHERE owner_id = ?', (owner,)).fetchone()[0] >= MAX_WISHES:
            db.rollback()
            flash(f'Your wishlist can hold up to {MAX_WISHES} games. Remove a game before saving another.', 'wishlist_error')
            return redirect(url_for('wishlist.index'), code=303)
        else:
            db.execute('INSERT INTO wishlist_games (owner_id,catalog_id,title,cover_image_id) VALUES (?,?,?,?)',
                       (owner, catalog_id, title, cover_image_id(game)))
            message = 'Added to your wishlist.'
        db.commit()
    except Exception:
        db.rollback()
        raise
    flash(message, 'wishlist_saved')
    return redirect(url_for('explore.game', catalog_id=catalog_id, _anchor='game-actions'), code=303)


@wishlist.post('/wishlist/games/<int:catalog_id>/remove')
def remove(catalog_id):
    catalog_id_valid(catalog_id)
    # The session is the only source of ownership; deletion remains available
    # even when the catalog provider has retired a game or is offline.
    get_db().execute('DELETE FROM wishlist_games WHERE owner_id = ? AND catalog_id = ?', (g.user['id'], catalog_id))
    flash('Removed from your wishlist.', 'wishlist_saved')
    if request.form.get('return_to') == 'game':
        return redirect(url_for('explore.game', catalog_id=catalog_id, _anchor='game-actions'), code=303)
    return redirect(url_for('wishlist.index'), code=303)


def page_context(owner):
    term = request.args.get('q', '').strip()
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)
    if len(term) > 200 or '\x00' in term or not 1 <= page <= 10000:
        abort(400)
    db = get_db()
    params = (owner, term)
    condition = 'owner_id = ? AND strpos(lower(title), lower(?)) > 0'
    total = db.execute('SELECT COUNT(*) FROM wishlist_games WHERE owner_id = ?', (owner,)).fetchone()[0]
    count = db.execute('SELECT COUNT(*) FROM wishlist_games WHERE ' + condition, params).fetchone()[0]
    if page > max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE):
        abort(404)
    rows = db.execute('SELECT catalog_id,title,cover_image_id FROM wishlist_games WHERE ' + condition
                      + ' ORDER BY created_at DESC,catalog_id DESC LIMIT ? OFFSET ?',
                      (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE)).fetchall()
    games = [{'catalog_id': row['catalog_id'], 'title': row['title'],
              'cover_url': collection_cover_url(row['cover_image_id'])} for row in rows]
    return {'wishes': games, 'total': total, 'count': count, 'query': term,
            'page': page, 'has_next': page * PAGE_SIZE < count}


@wishlist.get('/wishlist')
def index():
    profile = get_db().execute('SELECT display_name,username,is_public,share_wishlist FROM profiles WHERE id = ?', (g.user['id'],)).fetchone()
    return render_template('wishlist.html', wishlist_owner=True, wishlist_profile=profile, **page_context(g.user['id']))


@wishlist.get('/profile/<username>/wishlist')
def public(username):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,23}', username):
        abort(404)
    row = get_db().execute('SELECT p.id,p.display_name,p.username,p.is_public,p.share_wishlist FROM profile_usernames u JOIN profiles p ON p.id = u.owner_id WHERE u.username = ?', (username.lower(),)).fetchone()
    if not row:
        abort(404)
    if normal_owner() and str(row['id']) == g.user['id']:
        return redirect(url_for('wishlist.index'), code=302)
    if not row['is_public'] or not row['share_wishlist']:
        abort(404)
    if username != row['username']:
        return redirect(url_for('wishlist.public', username=row['username']), code=302)
    # Project only the public identity and saved catalog metadata into the page.
    return render_template('wishlist.html', wishlist_owner=False,
                           wishlist_profile={'display_name': row['display_name'], 'username': row['username']},
                           **page_context(row['id']))


def init_app(app):
    app.register_blueprint(wishlist)

    @app.after_request
    def wishlist_headers(response):
        if request.blueprint == 'wishlist':
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            response.headers['Referrer-Policy'] = 'same-origin'
        return response
