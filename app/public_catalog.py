"""Read-only public catalog browsing using cached IGDB data."""

from collections import deque
from threading import Lock
from time import monotonic

from flask import Blueprint, abort, current_app, g, redirect, render_template, url_for, request, jsonify

from app.catalog import CatalogError, get_catalog, game_suggestion, game_profile, collection_cover_url, cover_image_id, is_community_game
from app.catalog_journey import remember_selection, take_selection
from app.db import get_db
from app.ownership import owned
from app.game_reviews import review_context
from app.wishlist import wish_state


explore = Blueprint('explore', __name__, url_prefix='/explore')


class CatalogBudget:
    """Bound public requests per warm process; upstream also caches and throttles."""

    def __init__(self):
        self.requests = deque()
        self.lock = Lock()

    def allow(self, limit):
        with self.lock:
            now = monotonic()
            while self.requests and now - self.requests[0] >= 60:
                self.requests.popleft()
            if len(self.requests) >= limit:
                return False
            self.requests.append(now)
            return True


def public_request_allowed():
    budget = current_app.extensions.setdefault('public_catalog_budget', CatalogBudget())
    return budget.allow(current_app.config.get('PUBLIC_CATALOG_REQUEST_LIMIT', 60))


def catalog_card(game):
    suggestion = game_suggestion(game)
    return {**suggestion, 'name': suggestion['name'][:200],
            'community': is_community_game(game),
            'platforms': suggestion['platforms'][:60],
            'cover_url': collection_cover_url(cover_image_id(game))}


@explore.get('')
def index():
    term = request.args.get('q', '').strip()
    content = request.args.get('content', 'official')
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)
    if content not in ('official', 'all') or not 1 <= page <= 17:
        abort(400)
    total = 0
    games, error, status = [], None, 200
    if len(term) > 200:
        error, status = 'Search must contain no more than 200 characters.', 400
    elif len(term) >= 2:
        if not public_request_allowed():
            error, status = 'The catalog is busy. Please wait a minute and try again.', 429
        else:
            try:
                results = get_catalog().search_games(term, include_community=content == 'all')[:500]
                total = len(results)
                if page > max(1, (total + 29) // 30):
                    abort(404)
                games = [catalog_card(game) for game in results[(page - 1) * 30:page * 30]
                         if type(game.get('id')) is int and 0 < game['id'] < 2**63]
            except CatalogError:
                error, status = 'The catalog is temporarily unavailable. Please try again shortly.', 503
    return render_template('explore.html', query=term[:200], games=games, error=error,
                           content=content, page=page, total=total,
                           pages=max(1, (total + 29) // 30)), status


@explore.get('/suggestions')
def suggestions():
    term = request.args.get('q', '').strip()
    content = request.args.get('content', 'official')
    if content not in ('official', 'all'):
        return jsonify(error='Choose a valid catalog filter.'), 400
    if len(term) > 200:
        return jsonify(error='Search must contain no more than 200 characters.'), 400
    if len(term) < 2:
        return jsonify(games=[])
    if not public_request_allowed():
        return jsonify(error='The catalog is busy. Please wait a minute and try again.'), 429
    try:
        games = [catalog_card(game) for game in get_catalog().search_games(term, include_community=content == 'all', suggestions=True)[:10]
                 if type(game.get('id')) is int and 0 < game['id'] < 2**63]
    except CatalogError:
        return jsonify(error='The catalog is temporarily unavailable. Please try again shortly.'), 503
    return jsonify(games=games)


@explore.get('/games/<int:catalog_id>')
def game(catalog_id):
    if not 0 < catalog_id < 2**63:
        abort(404)
    item, profile, error, status = None, None, None, 200
    if not public_request_allowed():
        error, status = 'The catalog is busy. Please wait a minute and try again.', 429
    else:
        try:
            raw = get_catalog().get_game(catalog_id)
            if raw is None:
                error, status = 'This game is no longer available in the catalog.', 404
            else:
                item, profile = catalog_card(raw), game_profile(raw)
        except CatalogError:
            error, status = 'The catalog is temporarily unavailable. Please try again shortly.', 503
    can_manage = not current_app.config.get('AUTH_ENABLED') or bool(
        g.user and not g.account_session['recovery'] and g.profile and g.profile['display_name'].strip()
    )
    entries = []
    if item and can_manage:
        entries = get_db().execute(
            f'SELECT id, platform, status, rating FROM games WHERE igdb_id = ? AND {owned()} ORDER BY platform, id',
            (catalog_id,),
        ).fetchall()
    saved_platforms = {entry['platform'].strip().casefold() for entry in entries}
    available_platforms = [platform for platform in item['platforms'] if platform.strip().casefold() not in saved_platforms] if item else []
    return render_template('catalog_game.html', game=item, profile=profile, error=error,
                           can_manage=can_manage, entries=entries, available_platforms=available_platforms,
                           wishlist_saved=wish_state(catalog_id) if item else False,
                           **(review_context(catalog_id) if item else {})), status


@explore.get('/games/<int:catalog_id>/add')
def add(catalog_id):
    if not 0 < catalog_id < 2**63:
        abort(404)
    remember_selection(catalog_id)
    if current_app.config.get('AUTH_ENABLED'):
        if not g.user:
            return redirect(url_for('auth.login'))
        if g.account_session['recovery']:
            return redirect(url_for('auth.password'))
        if not g.profile or not g.profile['display_name'].strip():
            return redirect(url_for('auth.profile'))
    return redirect(url_for('main.create', igdb_id=take_selection()))


def init_app(app):
    app.register_blueprint(explore)

    @app.after_request
    def catalog_headers(response):
        if request.blueprint == 'explore':
            response.headers['Cache-Control'] = 'private, no-store'
            # HTTPS CSRF validation needs the Referer for our own form posts.
            # Cross-origin destinations still receive no browsing context.
            response.headers['Referrer-Policy'] = 'same-origin'
            if response.status_code == 429:
                response.headers['Retry-After'] = '60'
        return response
