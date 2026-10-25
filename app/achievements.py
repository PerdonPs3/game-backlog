"""Persistent, server-earned cosmetics and bounded owner-only notifications."""

import json

from flask import Blueprint, abort, current_app, g, jsonify, request

from app.db import get_db


achievements = Blueprint('achievements', __name__)
BADGES = tuple(
    {'key': key, 'name': key.title(), 'category': category, 'target': target,
     'description': description, 'icon': icon}
    for key, category, target, description, icon in (
        ('newcomer', 'collection', 1, 'Your first game collected', 'books'),
        ('collector', 'collection', 10, '10 games collected', 'books'),
        ('archivist', 'collection', 25, '25 games collected', 'books'),
        ('curator', 'collection', 50, '50 games collected', 'books'),
        ('legend', 'collection', 100, '100 games collected', 'books'),
        ('finisher', 'completion', 1, 'Your first game completed', 'trophy'),
        ('completionist', 'completion', 10, '10 games completed', 'trophy'),
        ('reviewer', 'reviews', 1, 'Your first public review', 'pen'),
        ('critic', 'reviews', 10, '10 public reviews', 'pen'),
    )
)
KEYS = {badge['key'] for badge in BADGES}


def normal_owner():
    return bool(current_app.config.get('AUTH_ENABLED') and getattr(g, 'user', None)
                and not g.account_session['recovery'] and g.profile
                and g.profile['display_name'].strip())


def reconcile(owner, *, in_transaction=False):
    """Award once under an account lock, including existing-account milestones.

    Collection milestones follow the library's game/platform entry counts.
    Private notes never contribute to review achievements. Deleting or changing
    entries does not revoke an already earned badge.
    """
    db = get_db()
    if not in_transaction:
        db.execute('BEGIN')
    try:
        db.execute('SELECT id FROM profiles WHERE id = ? FOR UPDATE', (owner,))
        row = db.execute("SELECT COUNT(*) AS collection, COUNT(*) FILTER (WHERE status = 'Completed') AS completion FROM games WHERE owner_id = ?", (owner,)).fetchone()
        counts = dict(row)
        counts['reviews'] = db.execute('SELECT COUNT(*) FROM public_game_reviews WHERE owner_id = ? AND moderation_hidden = FALSE', (owner,)).fetchone()[0]
        for badge in BADGES:
            if counts[badge['category']] >= badge['target']:
                db.execute('INSERT INTO profile_achievements (owner_id, badge_key) VALUES (?, ?) ON CONFLICT DO NOTHING', (owner, badge['key']))
        if not in_transaction:
            db.commit()
        return counts
    except Exception:
        if not in_transaction:
            db.rollback()
        raise


def owner_state():
    if not hasattr(g, 'achievement_state'):
        owner = g.user['id']
        counts = reconcile(owner)
        rows = get_db().execute('SELECT badge_key, earned_at, acknowledged_at FROM profile_achievements WHERE owner_id = ?', (owner,)).fetchall()
        selected = get_db().execute('SELECT featured_badges FROM profiles WHERE id = ?', (owner,)).fetchone()[0]
        g.achievement_state = build_context(rows, selected, counts)
    return g.achievement_state


def build_context(rows, selected, counts=None):
    earned = {row['badge_key']: row for row in rows}
    unlocked = [{**badge, 'earned_at': earned[badge['key']]['earned_at']} for badge in BADGES if badge['key'] in earned]
    if selected:
        chosen = json.loads(selected)
    else:
        # Initially feature the highest earned badge in each category.
        chosen = [next(b['key'] for b in reversed(unlocked) if b['category'] == category)
                  for category in ('collection', 'completion', 'reviews')
                  if any(b['category'] == category for b in unlocked)]
    featured = [next(b for b in unlocked if b['key'] == key) for key in chosen if key in earned]
    pending = [b for b in unlocked if earned[b['key']]['acknowledged_at'] is None]
    next_badge = next((dict(b, progress=min(counts[b['category']], b['target']))
                       for b in BADGES if b['key'] not in earned), None) if counts is not None else None
    return {'earned': unlocked, 'featured': featured, 'pending': pending, 'next': next_badge}


def public_badges(username):
    db = get_db()
    profile = db.execute('SELECT id, featured_badges FROM profiles WHERE username = ? AND is_public = TRUE AND share_badges = TRUE', (username,)).fetchone()
    if not profile:
        return None
    # Visitors never trigger awards or see progress, notifications, or owner IDs.
    rows = db.execute('SELECT badge_key, earned_at, acknowledged_at FROM profile_achievements WHERE owner_id = ?', (profile['id'],)).fetchall()
    context = build_context(rows, profile['featured_badges'])
    return {'earned': context['earned'], 'featured': context['featured'], 'next': None}


def save_features(db, owner, form):
    if form.get('badge_controls') != 'yes':
        return
    chosen = form.getlist('featured_badges')
    earned = {r[0] for r in db.execute('SELECT badge_key FROM profile_achievements WHERE owner_id = ?', (owner,))}
    if len(chosen) > 3 or len(chosen) != len(set(chosen)) or not set(chosen) <= earned:
        raise ValueError('Choose up to three badges you have already earned.')
    db.execute('UPDATE profiles SET featured_badges = ?, share_badges = ? WHERE id = ?',
               (json.dumps(chosen), form.get('share_badges') == 'yes', owner))


@achievements.post('/account/achievements/acknowledge')
def acknowledge():
    if not normal_owner():
        abort(403)
    keys = request.form.getlist('badge')
    if not keys or len(keys) > len(BADGES) or not set(keys) <= KEYS:
        abort(400)
    db = get_db()
    db.execute('BEGIN')
    try:
        for key in set(keys):
            db.execute('UPDATE profile_achievements SET acknowledged_at = COALESCE(acknowledged_at, CURRENT_TIMESTAMP AT TIME ZONE \'UTC\') WHERE owner_id = ? AND badge_key = ?', (g.user['id'], key))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify(ok=True)


def init_app(app):
    app.register_blueprint(achievements)

    @app.context_processor
    def achievement_context():
        return {'achievement_notice': owner_state()['pending'] if normal_owner() else []}



def award_current():
    """Persist awards within the collection mutation's existing transaction."""
    if normal_owner():
        reconcile(g.user['id'], in_transaction=True)
