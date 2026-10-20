"""Explicit, minimal public profile projections and owner-controlled publication."""

import re
from datetime import datetime, timezone

import psycopg
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app.catalog import collection_cover_url
from app.db import get_db


profiles = Blueprint('profiles', __name__)
USERNAME_WAIT_SECONDS = 30 * 24 * 60 * 60
RESERVED_NAMES = {'admin', 'administrator', 'api', 'auth', 'account', 'accounts', 'discover', 'explore', 'help', 'library', 'login', 'logout', 'moderator', 'official', 'players', 'profile', 'register', 'root', 'security', 'settings', 'staff', 'support', 'system', 'vestigium'}


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
    username = clean_username(form.get('username', ''))
    db.execute('BEGIN')
    try:
        profile = db.execute('SELECT username, username_changed_at FROM profiles WHERE id = ? FOR UPDATE', (owner,)).fetchone()
        if profile['username'] != username:
            now = username_clock(db)
            availability = username_availability(profile, now)
            if availability['locked']:
                raise ValueError('You can change your username again on ' + availability['available_at'] + '. You can still update your sharing settings.')
            claim_username(db, owner, username)
            db.execute('UPDATE profiles SET username_changed_at = ? WHERE id = ?', (now, owner))
        db.execute('UPDATE profiles SET username = ?, is_public = ?, share_bio = ?, share_showcase = ? WHERE id = ?',
                   (username, form.get('is_public') == 'yes', form.get('share_bio') == 'yes', form.get('share_showcase') == 'yes', owner))
        db.commit()
    except psycopg.errors.UniqueViolation:
        db.rollback()
        raise ValueError('That username is already taken. Choose another one.') from None
    except Exception:
        db.rollback()
        raise


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
    if request.method == 'POST':
        try:
            save_sharing(db, g.user['id'], request.form)
            flash('Sharing settings saved. Your profile is public.' if request.form.get('is_public') == 'yes' else 'Sharing settings saved. Your profile is private.', 'profile_saved')
            return redirect(url_for('profiles.sharing', _anchor='sharing-feedback'), code=303)
        except ValueError as exc:
            error = str(exc)
    item = db.execute('SELECT username, username_changed_at, is_public, share_bio, share_showcase FROM profiles WHERE id = ?', (g.user['id'],)).fetchone()
    return render_template('profile_sharing.html', sharing=item, error=error, username_state=username_availability(item, username_clock(db)))


@profiles.get('/players/<username>')
def public_profile(username):
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
    item = db.execute('SELECT display_name, username, avatar_color, CASE WHEN share_bio THEN bio ELSE \'\' END AS bio FROM profiles WHERE username = ? AND is_public = TRUE', (username,)).fetchone()
    if not item:
        abort(404)
    games = db.execute('SELECT g.title, g.platform, g.cover_image_id, g.igdb_id, s.position FROM profiles p JOIN profile_showcase s ON s.owner_id = p.id JOIN games g ON g.id = s.game_id AND g.owner_id = p.id WHERE p.username = ? AND p.is_public = TRUE AND p.share_showcase = TRUE ORDER BY s.position', (username,)).fetchall()
    showcase = [{'title': row['title'], 'platform': row['platform'], 'position': row['position'], 'catalog_id': row['igdb_id'], 'cover_url': collection_cover_url(row['cover_image_id'])} for row in games]
    return render_template('public_profile.html', profile=item, showcase=showcase)


def init_app(app):
    app.register_blueprint(profiles)

    @app.after_request
    def public_profile_headers(response):
        if request.endpoint == 'profiles.public_profile':
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            response.headers['Referrer-Policy'] = 'no-referrer'
        return response
