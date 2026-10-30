"""Owner-controlled connections without granting access to private profiles."""

import re

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app.db import get_db


following = Blueprint('following', __name__)
PAGE_SIZE = 20
VIEWS = {'followers': 'Followers', 'following': 'Following', 'requests': 'Follow requests',
         'sent': 'Sent requests', 'blocked': 'Blocked players'}


def viewer_id():
    return g.user['id'] if getattr(g, 'user', None) and not g.account_session['recovery'] else None


def unblocked_sql(alias, viewer):
    """Apply the same bilateral exclusion to rows, counts, and public projections."""
    if not viewer:
        return 'TRUE', ()
    return (f'NOT EXISTS (SELECT 1 FROM player_blocks b WHERE '
            f'(b.blocker_id = ? AND b.blocked_id = {alias}.id) OR '
            f'(b.blocked_id = ? AND b.blocker_id = {alias}.id))', (viewer, viewer))


def blocked(first, second):
    return bool(first and second and get_db().execute(
        'SELECT 1 FROM player_blocks WHERE (blocker_id = ? AND blocked_id = ?) '
        'OR (blocker_id = ? AND blocked_id = ?)', (first, second, second, first)).fetchone())


def save_privacy(db, owner, form):
    if form.get('connection_privacy_controls') == 'yes':
        db.execute('UPDATE profiles SET share_connections = ? WHERE id = ?',
                   (form.get('share_connections') == 'yes', owner))


def profile_context(username):
    if not username or not current_app.config.get('AUTH_ENABLED'):
        return {'connections': None}
    db = get_db()
    item = db.execute('SELECT id, is_public, share_connections FROM profiles WHERE username = ?', (username,)).fetchone()
    owner = bool(item and str(item['id']) == viewer_id())
    if not item or blocked(viewer_id(), item['id']):
        return {'connections': None}
    counts = {}
    if owner or (item['is_public'] and item['share_connections']):
        for kind in ('followers', 'following'):
            counts[kind] = connection_query(item['id'], kind, owner, count=True)
    state = None
    if viewer_id() and not owner:
        row = db.execute('SELECT state FROM player_follows WHERE follower_id = ? AND followed_id = ?',
                         (viewer_id(), item['id'])).fetchone()
        state = row['state'] if row else None
    return {'connections': {'username': username, 'owner': owner, 'counts': counts,
                            'state': state, 'signed_in': bool(viewer_id())}}


def connection_query(owner, kind, private, *, count=False, page=1):
    """Private identities are never included in public lists or their totals."""
    if kind == 'blocked':
        join, condition = 'player_blocks f JOIN profiles p ON p.id = f.blocked_id', 'f.blocker_id = ?'
    else:
        incoming = kind in ('followers', 'requests')
        join = 'player_follows f JOIN profiles p ON p.id = f.' + ('follower_id' if incoming else 'followed_id')
        condition = 'f.' + ('followed_id' if incoming else 'follower_id') + ' = ? AND f.state = ?'
    params = [owner]
    if kind != 'blocked':
        params.append('pending' if kind in ('requests', 'sent') else 'accepted')
    condition += ' AND p.username IS NOT NULL AND length(trim(p.display_name)) > 0'
    if not private:
        condition += ' AND p.is_public = TRUE'
    if kind != 'blocked':
        exclusion, values = unblocked_sql('p', viewer_id())
        condition += ' AND ' + exclusion
        params.extend(values)
    if count:
        return get_db().execute('SELECT COUNT(*) FROM ' + join + ' WHERE ' + condition, tuple(params)).fetchone()[0]
    # Even an owner's management list never reveals a private player's bio, photo,
    # or display name. The current handle is sufficient for relationship controls.
    public_identity = 'p.is_public' if kind != 'blocked' else 'FALSE'
    return get_db().execute(
        f"SELECT p.username, p.is_public, CASE WHEN {public_identity} THEN p.display_name ELSE 'Private player' END AS display_name, "
        f"CASE WHEN {public_identity} THEN p.avatar_color ELSE '#64748b' END AS avatar_color, "
        f'({public_identity} AND p.share_photo AND p.avatar_image IS NOT NULL) AS has_public_photo, '
        f"CASE WHEN {public_identity} AND p.share_bio THEN left(p.bio, 140) ELSE '' END AS bio, "
        f'CASE WHEN {public_identity} THEN p.country_code ELSE NULL END AS country_code, '
        f'CASE WHEN {public_identity} THEN p.admin_badge ELSE FALSE END AS admin_badge, '
        '(SELECT own.state FROM player_follows own WHERE own.follower_id = ? AND own.followed_id = p.id) AS follow_state '
        'FROM ' + join + ' WHERE ' + condition + ' ORDER BY f.created_at DESC, p.username LIMIT ? OFFSET ?',
        (viewer_id(), *params, PAGE_SIZE, (page - 1) * PAGE_SIZE)).fetchall()


def page_number():
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)
    if not 1 <= page <= 10000:
        abort(400)
    return page


@following.before_request
def require_account():
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    if request.endpoint == 'following.public_list':
        return
    if not g.user:
        return redirect(url_for('auth.login'))
    if g.account_session['recovery']:
        return redirect(url_for('auth.password'))
    if not g.profile or not g.profile['display_name'].strip() or not g.profile['username']:
        return redirect(url_for('auth.profile'))


@following.get('/account/connections')
def manage():
    kind = request.args.get('view', 'followers')
    if kind not in VIEWS:
        abort(400)
    page = page_number()
    totals = {view: connection_query(g.user['id'], view, True, count=True) for view in VIEWS}
    count = totals[kind]
    if page > max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE):
        abort(404)
    return render_template('connections.html', connection_owner=True, kind=kind, title=VIEWS[kind],
                           players=connection_query(g.user['id'], kind, True, page=page),
                           total=count, page=page, has_next=page * PAGE_SIZE < count, views=VIEWS, totals=totals)


@following.get('/profile/<username>/connections/<kind>')
def public_list(username, kind):
    if kind not in ('followers', 'following') or not re.fullmatch(r'[a-z][a-z0-9_]{2,23}', username):
        abort(404)
    item = get_db().execute('SELECT id, is_public, share_connections FROM profiles WHERE username = ?', (username,)).fetchone()
    if not item or blocked(viewer_id(), item['id']):
        abort(404)
    if str(item['id']) == viewer_id():
        return redirect(url_for('following.manage', view=kind), code=302)
    if not item['is_public'] or not item['share_connections']:
        abort(404)
    page = page_number()
    count = connection_query(item['id'], kind, False, count=True)
    if page > max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE):
        abort(404)
    return render_template('connections.html', connection_owner=False, kind=kind, title=VIEWS[kind],
                           players=connection_query(item['id'], kind, False, page=page),
                           total=count, page=page, has_next=page * PAGE_SIZE < count, username=username)


@following.post('/account/connections/follow')
def follow_by_username():
    return change(request.form.get('username', '').strip().lstrip('@').lower(), 'follow')


@following.post('/connections/<username>/<action>')
def change(username, action):
    actions = {'follow', 'unfollow', 'cancel', 'approve', 'decline', 'remove', 'block', 'unblock'}
    if action not in actions or not re.fullmatch(r'[a-z][a-z0-9_]{2,23}', username):
        abort(400)
    db = get_db()
    actor = g.user['id']
    target = db.execute('SELECT id FROM profiles WHERE username = ? AND length(trim(display_name)) > 0', (username,)).fetchone()
    if target and str(target['id']) == actor:
        abort(400)
    db.execute('BEGIN')
    try:
        # Lock both accounts in a stable order. Follow, approval, blocking, and
        # profile privacy saves cannot race to recreate a blocked relationship.
        rows = db.execute('SELECT id, is_public FROM profiles WHERE id = ? OR id = ? ORDER BY id FOR UPDATE',
                          (actor, target['id'] if target else actor)).fetchall()
        if action == 'follow':
            count = db.execute("SELECT COUNT(*) FROM player_follow_events WHERE owner_id = ? AND created_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '1 hour'", (actor,)).fetchone()[0]
            if count >= current_app.config.get('FOLLOW_REQUEST_LIMIT', 30):
                db.rollback()
                response = current_app.make_response(('Too many follow requests. Try again in an hour.', 429))
                response.headers['Retry-After'] = '3600'
                return response
            db.execute("DELETE FROM player_follow_events WHERE owner_id = ? AND created_at <= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - INTERVAL '1 hour'", (actor,))
            db.execute('INSERT INTO player_follow_events (owner_id) VALUES (?)', (actor,))
        target_row = next((row for row in rows if target and row['id'] == target['id']), None)
        if not target_row:
            if action != 'follow':
                abort(404)
        elif action == 'unblock':
            db.execute('DELETE FROM player_blocks WHERE blocker_id = ? AND blocked_id = ?', (actor, target['id']))
        elif action == 'block':
            db.execute('INSERT INTO player_blocks (blocker_id, blocked_id) VALUES (?, ?) ON CONFLICT DO NOTHING', (actor, target['id']))
            db.execute('DELETE FROM player_follows WHERE (follower_id = ? AND followed_id = ?) OR (follower_id = ? AND followed_id = ?)',
                       (actor, target['id'], target['id'], actor))
        elif not blocked(actor, target['id']):
            if action == 'follow':
                db.execute('INSERT INTO player_follows (follower_id, followed_id, state) VALUES (?, ?, ?) ON CONFLICT DO NOTHING',
                           (actor, target['id'], 'accepted' if target_row['is_public'] else 'pending'))
            elif action in ('unfollow', 'cancel'):
                db.execute('DELETE FROM player_follows WHERE follower_id = ? AND followed_id = ?', (actor, target['id']))
            elif action == 'approve':
                db.execute("UPDATE player_follows SET state = 'accepted' WHERE follower_id = ? AND followed_id = ? AND state = 'pending'", (target['id'], actor))
            else:
                db.execute('DELETE FROM player_follows WHERE follower_id = ? AND followed_id = ? AND state = ?',
                           (target['id'], actor, 'pending' if action == 'decline' else 'accepted'))
        db.commit()
    except Exception:
        db.rollback()
        raise
    messages = {'follow': 'Follow request saved if this player is available.', 'unfollow': 'No longer following.',
                'cancel': 'Follow request cancelled.', 'approve': 'Follow request approved.', 'decline': 'Follow request declined.',
                'remove': 'Follower removed.', 'block': 'Player blocked. Connections and requests in both directions were removed.',
                'unblock': 'Player unblocked. Previous connections were not restored.'}
    return_to_profile = (request.form.get('return_to') == 'profile' and action not in ('block', 'unblock')
                         and target_row and target_row['is_public'] and not blocked(actor, target['id']))
    follow_from_card = (request.form.get('return_to') == 'connections' and target_row
                        and target_row['is_public'] and not blocked(actor, target['id']))
    if (return_to_profile or follow_from_card) and action == 'follow':
        state = db.execute('SELECT state FROM player_follows WHERE follower_id = ? AND followed_id = ?', (actor, target['id'])).fetchone()
        messages['follow'] = 'You are now following @' + username + '.' if state and state['state'] == 'accepted' else 'Follow request pending approval.'
    flash(messages[action], 'connections_saved')
    if return_to_profile:
        return redirect(url_for('profiles.public_profile', username=username), code=303)
    kind = request.form.get('view', 'following')
    return redirect(url_for('following.manage', view=kind if kind in VIEWS else 'following'), code=303)


def init_app(app):
    app.register_blueprint(following)

    @app.before_request
    def protect_blocked_public_content():
        if not current_app.config.get('AUTH_ENABLED') or not viewer_id():
            return
        if request.endpoint in ('profiles.public_profile', 'profiles.public_photo', 'wishlist.public', 'backgrounds.public_image'):
            username = (request.view_args or {}).get('username', '').lower()
            # Resolve aliases before redirecting, so old links cannot reveal a
            # blocked player's new identity.
            row = get_db().execute('SELECT owner_id FROM profile_usernames WHERE username = ?', (username,)).fetchone()
            if row and blocked(viewer_id(), row['owner_id']):
                abort(404)

    @app.after_request
    def connection_headers(response):
        if request.blueprint == 'following':
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            response.headers['Referrer-Policy'] = 'same-origin'
            response.vary.add('Cookie')
        return response
