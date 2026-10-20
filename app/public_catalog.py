"""Anonymous, read-only catalog pages using the existing cached IGDB client."""

from collections import deque
from threading import Lock
from time import monotonic

from flask import Blueprint, abort, current_app, g, redirect, render_template, url_for, request

from app.catalog import CatalogError, get_catalog, game_suggestion, game_profile, collection_cover_url, cover_image_id
from app.catalog_journey import remember_selection, take_selection


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
            'platforms': suggestion['platforms'][:60],
            'cover_url': collection_cover_url(cover_image_id(game))}


@explore.get('')
def index():
    term = request.args.get('q', '').strip()
    games, error, status = [], None, 200
    if len(term) > 200:
        error, status = 'Search must contain no more than 200 characters.', 400
    elif len(term) >= 2:
        if not public_request_allowed():
            error, status = 'The catalog is busy. Please wait a minute and try again.', 429
        else:
            try:
                games = [catalog_card(game) for game in get_catalog().search_games(term)[:30]
                         if type(game.get('id')) is int and 0 < game['id'] < 2**63]
            except CatalogError:
                error, status = 'The catalog is temporarily unavailable. Please try again shortly.', 503
    return render_template('explore.html', query=term[:200], games=games, error=error), status


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
    return render_template('catalog_game.html', game=item, profile=profile, error=error), status


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
            response.headers['Referrer-Policy'] = 'no-referrer'
            if response.status_code == 429:
                response.headers['Retry-After'] = '60'
        return response
