"""Explicit, minimal public profile projections and owner-controlled publication."""

import re
from datetime import datetime, timezone

import psycopg
from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, url_for

from app.achievements import public_badges
from app.catalog import collection_cover_url
from app.game_reviews import profile_review_context
from app.db import get_db


profiles = Blueprint('profiles', __name__)
USERNAME_WAIT_SECONDS = 30 * 24 * 60 * 60
RESERVED_NAMES = {'admin', 'administrator', 'api', 'auth', 'account', 'accounts', 'discover', 'explore', 'help', 'library', 'login', 'logout', 'moderator', 'official', 'players', 'profile', 'register', 'root', 'security', 'settings', 'staff', 'support', 'system', 'vestigium'}


@profiles.get('/players')
def search():
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    from app.public_catalog import CatalogBudget
    term = request.args.get('q', '').strip()
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)
    if not 1 <= page <= 10000 or len(term) > 80 or '\x00' in term:
        abort(400)
    players, count, error = [], 0, None
    status = 200
    if term:
        if len(term.lstrip('@')) < 2:
            error, status = 'Enter at least two characters.', 400
        elif not current_app.extensions.setdefault('public_player_budget', CatalogBudget()).allow(current_app.config.get('PUBLIC_PLAYER_REQUEST_LIMIT', 60)):
            error, status = 'Player search is busy. Please try again shortly.', 429
        else:
            db = get_db()
            term = term.lstrip('@')
            from app.following import unblocked_sql, viewer_id
            exclusion, values = unblocked_sql('profiles', viewer_id())
            condition = "is_public = TRUE AND username IS NOT NULL AND length(trim(display_name)) > 0 AND (strpos(lower(display_name), lower(?)) > 0 OR strpos(username, lower(?)) > 0) AND " + exclusion
            count = db.execute('SELECT COUNT(*) FROM profiles WHERE ' + condition, (term, term, *values)).fetchone()[0]
            players = db.execute('SELECT display_name, username, avatar_color, country_code, admin_badge, (share_photo AND avatar_image IS NOT NULL) AS has_public_photo FROM profiles WHERE ' + condition + ' ORDER BY CASE WHEN username = lower(?) THEN 0 ELSE 1 END, lower(display_name), username LIMIT 20 OFFSET ?', (term, term, *values, term, (page - 1) * 20)).fetchall()
    response = current_app.make_response((render_template('players.html', players=players, query=term, total=count, page=page, has_next=page * 20 < count, error=error), status))
    if status == 429:
        response.headers['Retry-After'] = '60'
    return response


def clean_username(value):
    username = value.strip().lower()
    if not re.fullmatch(r'[a-z][a-z0-9_]{2,23}', username) or username in RESERVED_NAMES:
        raise ValueError('Choose an available username with 3–24 letters, numbers, or underscores, starting with a letter. Links use lowercase letters.')
    return username


def username_clock(db):
    return db.execute('SELECT FLOOR(EXTRACT(EPOCH FROM clock_timestamp()))::BIGINT').fetchone()[0]


def claim_username(db, owner, username):
    """Reserve current names and aliases in one namespace inside a transaction."""
    claimed = db.execute('INSERT INTO profile_usernames (username, owner_id) VALUES (?, ?) '
                         'ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username '
                         'WHERE profile_usernames.owner_id = EXCLUDED.owner_id RETURNING owner_id',
                         (username, owner)).fetchone()
    if not claimed:
        raise ValueError('That username is already taken or reserved by a previous profile link. Choose another one.')


def username_availability(profile, now):
    available_at = (profile['username_changed_at'] + USERNAME_WAIT_SECONDS) if profile['username_changed_at'] is not None else 0
    return {
        'locked': bool(profile['username'] and available_at > now),
        'available_at': datetime.fromtimestamp(available_at, timezone.utc).strftime('%Y-%m-%d at %H:%M:%S UTC') if available_at else None,
        'available_iso': datetime.fromtimestamp(available_at, timezone.utc).isoformat() if available_at else None,
    }


def save_sharing(db, owner, form):
    db.execute('BEGIN')
    try:
        update_sharing(db, owner, form)
        db.commit()
    except psycopg.errors.UniqueViolation:
        db.rollback()
        raise ValueError('That username is already taken. Choose another one.') from None
    except Exception:
        db.rollback()
        raise


def update_sharing(db, owner, form):
    """Update identity and privacy inside the caller's atomic profile transaction."""
    username = clean_username(form.get('username', ''))
    profile = db.execute('SELECT username, username_changed_at, share_statistics, share_activity FROM profiles WHERE id = ? FOR UPDATE', (owner,)).fetchone()
    if profile['username'] != username:
        now = username_clock(db)
        availability = username_availability(profile, now)
        if availability['locked']:
            raise ValueError('You can change your username again on ' + availability['available_at'] + '. You can still update your sharing settings.')
        claim_username(db, owner, username)
        db.execute('UPDATE profiles SET username_changed_at = ? WHERE id = ?', (now, owner))
    db.execute('UPDATE profiles SET username = ?, is_public = ?, share_bio = ?, share_showcase = ? WHERE id = ?',
               (username, form.get('is_public') == 'yes', form.get('share_bio') == 'yes', form.get('share_showcase') == 'yes', owner))
    # Older forms do not carry these controls; preserve their current choices.
    for field in ('share_statistics', 'share_activity'):
        if form.get('profile_activity_controls') == 'yes' or field in form:
            db.execute(f'UPDATE profiles SET {field} = ? WHERE id = ?', (form.get(field) == 'yes', owner))
    from app.wishlist import save_privacy
    save_privacy(db, owner, form)
    from app.following import save_privacy as save_connection_privacy
    save_connection_privacy(db, owner, form)
    if form.get('publish_photo') == 'yes':
        db.execute('UPDATE profiles SET share_photo = avatar_image IS NOT NULL WHERE id = ?', (owner,))


@profiles.route('/account/profile/sharing', methods=['GET', 'POST'])
def sharing():
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    if not g.user:
        return redirect(url_for('auth.login'))
    if g.account_session['recovery']:
        return redirect(url_for('auth.password'))
    if not g.profile or not g.profile['display_name'].strip():
        return redirect(url_for('auth.profile'))
    db = get_db()
    error = None
    if request.method == 'GET':
        return redirect(url_for('auth.profile', _anchor='profile-privacy'), code=302)
    if request.method == 'POST':
        try:
            save_sharing(db, g.user['id'], request.form)
            g.profile = db.execute('SELECT display_name, username FROM profiles WHERE id = ?', (g.user['id'],)).fetchone()
            flash('Sharing settings saved. Your profile is public.' if request.form.get('is_public') == 'yes' else 'Sharing settings saved. Your profile is private.', 'profile_saved')
            return redirect(url_for('profiles.sharing', _anchor='sharing-feedback'), code=303)
        except ValueError as exc:
            error = str(exc)
    item = db.execute('SELECT username, username_changed_at, is_public, share_bio, share_showcase, share_statistics, share_activity FROM profiles WHERE id = ?', (g.user['id'],)).fetchone()
    return render_template('profile_sharing.html', sharing=item, error=error, username_state=username_availability(item, username_clock(db)))


@profiles.get('/players/<username>')
@profiles.get('/profile/<username>')
def public_profile(username):
    if request.path.startswith('/profile/'):
        if not current_app.config.get('AUTH_ENABLED') or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,23}', username):
            abort(404)
        username = username.lower()
        identity = get_db().execute('SELECT p.id, p.username FROM profile_usernames u JOIN profiles p ON p.id = u.owner_id WHERE u.username = ?', (username,)).fetchone()
        if not identity:
            abort(404)
        is_owner = bool(g.user and str(identity['id']) == g.user['id'] and not g.account_session['recovery'])
        if not is_owner and not get_db().execute('SELECT 1 FROM profiles WHERE id = ? AND is_public = TRUE', (identity['id'],)).fetchone():
            abort(404)
        if request.view_args['username'] != identity['username']:
            return redirect(url_for('profiles.public_profile', username=identity['username']), code=302)
        if is_owner:
            from app.auth import profile_overview
            return profile_overview()
    if not current_app.config.get('AUTH_ENABLED') or not re.fullmatch(r'[a-z][a-z0-9_]{2,23}', username):
        abort(404)
    db = get_db()
    identity = db.execute('SELECT p.username FROM profile_usernames u JOIN profiles p ON p.id = u.owner_id WHERE u.username = ? AND p.is_public = TRUE', (username,)).fetchone()
    if not identity:
        abort(404)
    if identity['username'] != username:
        # Temporary, non-cacheable redirects respect later privacy changes and
        # always resolve directly to the current name, never an alias chain.
        return redirect(url_for('profiles.public_profile', username=identity['username']), code=302)
    # Project only explicitly shared fields; never pass the private profile or game row.
    item = db.execute('SELECT display_name, username, avatar_color, CASE WHEN share_bio THEN bio ELSE \'\' END AS bio, country_code, admin_badge, CASE WHEN share_background THEN background_key ELSE \'obsidian\' END AS background_key, share_wishlist, (share_photo AND avatar_image IS NOT NULL) AS has_public_photo FROM profiles WHERE username = ? AND is_public = TRUE', (username,)).fetchone()
    if not item:
        abort(404)
    games = db.execute('SELECT g.title, g.platform, g.cover_image_id, g.igdb_id, s.position FROM profiles p JOIN profile_showcase s ON s.owner_id = p.id JOIN games g ON g.id = s.game_id AND g.owner_id = p.id WHERE p.username = ? AND p.is_public = TRUE AND p.share_showcase = TRUE ORDER BY s.position', (username,)).fetchall()
    showcase = [{'title': row['title'], 'platform': row['platform'], 'position': row['position'], 'catalog_id': row['igdb_id'], 'cover_url': collection_cover_url(row['cover_image_id'])} for row in games]
    from app.following import profile_context
    return render_template('public_profile.html', profile=item, badge_state=public_badges(username), profile_owner=False, showcase=showcase, **public_activity_context(username), **profile_review_context(username), **profile_context(username))


def public_activity_context(username):
    """Expose only the enabled aggregate and bounded activity projections."""
    db = get_db()
    row = db.execute("SELECT COUNT(g.id) AS total, COUNT(g.id) FILTER (WHERE g.status = 'Completed') AS completed, "
                     "COUNT(g.id) FILTER (WHERE g.status = 'Playing') AS playing, AVG(g.rating) AS average "
                     'FROM profiles p LEFT JOIN games g ON g.owner_id = p.id '
                     'WHERE p.username = ? AND p.is_public = TRUE AND p.share_statistics = TRUE GROUP BY p.id', (username,)).fetchone()
    stats = dict(row) if row else None
    if stats is not None:
        stats['completion_percent'] = int(stats['completed'] * 100 / stats['total'] + .5) if stats['total'] else 0
    activity_enabled = bool(db.execute('SELECT 1 FROM profiles WHERE username = ? AND is_public = TRUE AND share_activity = TRUE', (username,)).fetchone())
    playing, completed = [], []
    if activity_enabled:
        for status, target, order in [('Playing', playing, 'g.started_on DESC NULLS LAST, g.created_at DESC, g.id DESC'),
                                      ('Completed', completed, 'g.completed_on DESC, g.id DESC')]:
            rows = db.execute('SELECT g.title, g.platform, g.rating, g.igdb_id AS catalog_id, g.cover_image_id, g.completed_on '
                              'FROM games g JOIN profiles p ON p.id = g.owner_id '
                              'WHERE p.username = ? AND p.is_public = TRUE AND p.share_activity = TRUE AND g.status = ? '
                              + ('AND g.completed_on IS NOT NULL ' if status == 'Completed' else '')
                              + 'ORDER BY ' + order + ' LIMIT 3', (username, status)).fetchall()
            target.extend({'title': r['title'], 'platform': r['platform'], 'rating': r['rating'], 'catalog_id': r['catalog_id'],
                           'completed_on': r['completed_on'] if status == 'Completed' else None,
                           'cover_url': collection_cover_url(r['cover_image_id'])} for r in rows)
    return {'public_stats': stats, 'public_activity_enabled': activity_enabled, 'public_playing': playing, 'public_completed': completed}


@profiles.get('/players/<username>/photo')
def public_photo(username):
    if not current_app.config.get('AUTH_ENABLED') or not re.fullmatch(r'[a-z][a-z0-9_]{2,23}', username):
        abort(404)
    # Re-check visibility and publication on every request, including direct URLs.
    image = get_db().execute('SELECT avatar_image FROM profiles WHERE username = ? AND is_public = TRUE AND share_photo = TRUE AND avatar_image IS NOT NULL', (username,)).fetchone()
    if not image:
        abort(404)
    response = Response(bytes(image['avatar_image']), mimetype='image/jpeg')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def init_app(app):
    app.register_blueprint(profiles)

    @app.after_request
    def public_profile_headers(response):
        if request.endpoint in ('profiles.public_profile', 'profiles.public_photo', 'profiles.search'):
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            response.headers['Referrer-Policy'] = 'same-origin' if request.endpoint == 'profiles.public_profile' else 'no-referrer'
        return response
