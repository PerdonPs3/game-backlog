"""Canonical destinations and bounded, same-origin navigation context."""

import re
import unicodedata
from time import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from flask import current_app, g, has_request_context, request, session, url_for
from werkzeug.exceptions import HTTPException


ORIGIN_ENDPOINTS = {'main.index', 'main.lists', 'main.pick_game', 'main.game_details',
                    'wishlist.index', 'wishlist.public', 'discovery.index', 'explore.index',
                    'explore.game', 'profiles.search', 'profiles.public_profile',
                    'following.manage', 'following.public_list', 'navigation.data'}
QUERY_KEYS = {'q', 'status', 'sort', 'list', 'mode', 'genre', 'platform', 'page',
              'view', 'content', 'reviews_page', 'status_filter', 'pick', 'game', 'igdb_id'}


def safe_destination(value, depth=0, allowed=None):
    if not isinstance(value, str) or not value or len(value) > 1600 or depth > 2:
        return None
    if any(ord(char) < 32 for char in value) or '\\' in value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return None
    try:
        endpoint, _ = current_app.url_map.bind('').match(parsed.path, method='GET')
    except HTTPException:
        return None
    if endpoint not in (allowed or ORIGIN_ENDPOINTS):
        return None
    values = []
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=30)
    except ValueError:
        return None
    for key, item in pairs:
        if key in QUERY_KEYS and len(item) <= 200 and not any(ord(char) < 32 for char in item):
            values.append((key, item))
        elif key == 'from':
            nested = safe_destination(item, depth + 1)
            if nested:
                values.append((key, nested))
    fragment = parsed.fragment if re.fullmatch(r'[A-Za-z0-9_-]{1,60}', parsed.fragment) else ''
    return parsed.path + ('?' + urlencode(values) if values else '') + ('#' + fragment if fragment else '')


def pending_login_destination():
    saved = session.get('navigation_login')
    if (isinstance(saved, dict) and type(saved.get('at')) is int
            and 0 <= time() - saved['at'] <= 1800):
        return safe_destination(saved.get('path'), allowed=ORIGIN_ENDPOINTS | {'main.create', 'main.edit', 'main.import_backup', 'auth.profile', 'auth.edit_showcase'})
    return None


def remember_login_destination():
    if request.method == 'GET':
        target = safe_destination(request.full_path.rstrip('?'), allowed=ORIGIN_ENDPOINTS | {'main.create', 'main.edit', 'main.import_backup', 'auth.profile', 'auth.edit_showcase'})
        if target:
            session['navigation_login'] = {'path': target, 'at': int(time())}


def take_login_destination():
    target = pending_login_destination()
    session.pop('navigation_login', None)
    return target


def navigation_origin():
    if not has_request_context():
        return None
    return safe_destination(request.path + ('?' + request.query_string.decode('ascii', errors='replace') if request.query_string else ''))


def navigation_return(default=None):
    return (safe_destination(request.form.get('return_path'))
            or safe_destination(request.args.get('from'))
            or default or getattr(g, 'navigation_default', None) or url_for('main.index'))


def game_slug(title):
    clean = unicodedata.normalize('NFKD', str(title)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', clean).strip('-')[:100] or 'game'


def navigation_return_label():
    target = navigation_return()
    try:
        endpoint, _ = current_app.url_map.bind('').match(urlsplit(target).path, method='GET')
    except HTTPException:
        return 'Back to Library'
    if endpoint in ('discovery.index', 'explore.index'):
        return 'Back to Discover'
    if endpoint.startswith('wishlist.'):
        return 'Back to Wishlist'
    if endpoint == 'explore.game':
        return 'Back to game'
    if endpoint == 'profiles.public_profile':
        return 'Back to profile'
    if endpoint.startswith(('following.', 'profiles.')):
        return 'Back to Community'
    if endpoint == 'navigation.data':
        return 'Back to Settings'
    return 'Back to Library'


def game_url(catalog_id, title=None, *, origin=True, section=None):
    values = {'catalog_id': catalog_id, 'slug': game_slug(title) if title else 'game'}
    if origin is True:
        source = navigation_origin() or (safe_destination(request.args.get('from')) if has_request_context() else None)
    else:
        source = safe_destination(origin) if origin else None
    if source:
        values['from'] = source
    if section:
        values['_anchor'] = section
    return url_for('explore.game', **values)


LIBRARY_SECTIONS = {'main.index', 'wishlist.index', 'main.lists', 'main.pick_game'}


def library_home_url():
    """Carry collection filters through sibling tabs without storing private queries."""
    if hasattr(g, 'library_home'):
        return g.library_home
    source = navigation_origin() if request.endpoint == 'main.index' else safe_destination(request.args.get('from'))
    values = {}
    if source:
        parsed = urlsplit(source)
        try:
            endpoint, _ = current_app.url_map.bind('').match(parsed.path, method='GET')
        except HTTPException:
            endpoint = None
        if endpoint == 'main.index':
            from app.game_fields import STATUSES
            from app.db import get_db
            from app.ownership import owned
            options = dict(parse_qsl(parsed.query))
            if options.get('q') and len(options['q']) <= 200:
                values['q'] = options['q']
            if options.get('status') in STATUSES:
                values['status'] = options['status']
            if options.get('sort') in ('oldest', 'title', 'rating'):
                values['sort'] = options['sort']
            list_id = options.get('list', '')
            if (list_id.isascii() and list_id.isdigit() and len(list_id) <= 18
                    and get_db().execute(f'SELECT 1 FROM game_lists WHERE id = ? AND {owned()}', (int(list_id),)).fetchone()):
                values['list'] = list_id
    g.library_home = url_for('main.index', **values)
    return g.library_home


def library_section_url(endpoint, **values):
    if endpoint not in LIBRARY_SECTIONS:
        raise ValueError('Choose a library section.')
    if endpoint == 'main.index':
        return library_home_url()
    home = library_home_url()
    if '?' in home:
        values['from'] = home
    return url_for(endpoint, **values)


def init_app(app):
    app.jinja_env.globals.update(game_url=game_url, navigation_return=navigation_return,
                                navigation_origin=navigation_origin,
                                library_home_url=library_home_url, library_section_url=library_section_url)
    @app.url_defaults
    def navigation_defaults(endpoint, values):
        if endpoint == 'explore.game':
            values.setdefault('slug', 'game')
        if endpoint in ('main.edit', 'main.create', 'main.delete', 'explore.add') and 'from' not in values:
            source = navigation_origin()
            if source:
                if request.endpoint == 'explore.game' and endpoint in ('main.edit', 'main.delete'):
                    source = source.split('#', 1)[0] + '#your-progress'
                values['from'] = source
        if endpoint == 'main.create' and 'igdb_id' in values:
            values['game'] = values.pop('igdb_id')

    @app.context_processor
    def navigation_context():
        endpoint = request.endpoint or ''
        group = 'discover' if endpoint.startswith(('explore.', 'discovery.')) else 'community' if endpoint.startswith(('profiles.', 'following.')) else 'library'
        if endpoint in ('auth.profile', 'auth.edit_showcase', 'main.export_backup', 'main.import_backup', 'navigation.data'):
            group = 'settings'
        profile = getattr(g, 'profile', None)
        library_section = endpoint in LIBRARY_SECTIONS
        library_total = 0
        if library_section and endpoint != 'main.index' and (not current_app.config.get('AUTH_ENABLED') or normal_owner()):
            from app.db import get_db
            from app.ownership import owned
            library_total = get_db().execute(f'SELECT COUNT(*) FROM games WHERE {owned()}').fetchone()[0]
        return {'game_url': game_url, 'navigation_return': navigation_return,
                'navigation_return_label': navigation_return_label,
                'navigation_origin': navigation_origin, 'navigation_group': group,
                'library_section': library_section, 'library_total': library_total,
                'navigation_initial': ((profile['display_name'] if profile else 'You') or 'You')[:1].upper()}

    from flask import render_template, redirect
    from app.achievements import normal_owner

    def data():
        if app.config.get('AUTH_ENABLED') and not normal_owner():
            return redirect(url_for('auth.login' if not g.user else 'auth.password' if g.account_session['recovery'] else 'auth.profile'))
        return render_template('account_data.html')

    app.add_url_rule('/settings/data', endpoint='navigation.data', view_func=data)
    app.add_url_rule('/community', endpoint='navigation.community', view_func=lambda: redirect(url_for('profiles.search')))
