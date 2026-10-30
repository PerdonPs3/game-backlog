"""Compatibility aliases retain session ownership; private URLs omit usernames."""

import re
from flask import abort, current_app, g, redirect, request, url_for
from app.db import get_db

ACCOUNT_PAGES = {
    'wishlist.index': '/account/<username>/wishlist',
    'main.index': '/account/<username>/library',
    'auth.profile_overview': '/account/<username>/profile',
    'auth.profile': '/account/<username>/profile/edit',
    'auth.edit_showcase': '/account/<username>/profile/showcase',
    'profiles.sharing': '/account/<username>/profile/sharing',
}
ALIASES = {
    'main.lists': '/lists', 'main.edit_list': '/lists/<int:list_id>/edit',
    'main.delete_list': '/lists/<int:list_id>/delete',
    'main.game_details': '/games/<int:game_id>', 'main.edit': '/games/<int:game_id>/edit',
    'main.delete': '/games/<int:game_id>/delete', 'main.create': '/games/new',
    'main.pick_game': '/games/pick', 'main.export_backup': '/backups/export',
    'main.import_backup': '/backups/import', 'auth.profile': '/account/profile/edit',
    'auth.edit_showcase': '/account/profile/showcase', 'wishlist.index': '/wishlist',
    'following.manage': '/account/connections', 'profiles.search': '/players',
    'profiles.public_profile': '/profile/<username>',
    'profiles.public_photo': '/profile/<username>/photo',
    'backgrounds.public_image': '/profile/<username>/background',
    'wishlist.public': '/profile/<username>/wishlist',
    'following.public_list': '/profile/<username>/connections/<kind>',
    'explore.index': '/explore', 'explore.game': '/explore/games/<int:catalog_id>',
}


def current_username():
    profile = getattr(g, 'profile', None)
    recovery = (getattr(g, 'account_session', None) or {}).get('recovery')
    if getattr(g, 'user', None) and profile and profile['display_name'].strip() and not recovery:
        return profile['username']
    return None


def init_app(app):
    for endpoint, path in [*ALIASES.items(), *ACCOUNT_PAGES.items()]:
        original = next(rule for rule in app.url_map.iter_rules(endpoint))
        methods = sorted(original.methods - {'OPTIONS', 'HEAD'})
        options = {'defaults': {'slug': None}} if endpoint == 'explore.game' else {}
        app.add_url_rule(path, endpoint=endpoint, view_func=app.view_functions[endpoint], methods=methods, **options)

    @app.url_value_preprocessor
    def old_account_values(endpoint, values):
        if endpoint in ACCOUNT_PAGES and values is not None:
            g.account_path_username = values.pop('username', None)

    @app.url_defaults
    def public_profile_defaults(endpoint, values):
        if endpoint in ACCOUNT_PAGES:
            values.pop('username', None)
        if endpoint == 'profiles.public_profile' and 'username' not in values:
            username = current_username()
            if username:
                values['username'] = username

    @app.before_request
    def validate_old_account_identity():
        if request.endpoint not in ACCOUNT_PAGES:
            return
        requested = getattr(g, 'account_path_username', None)
        if not current_app.config.get('AUTH_ENABLED'):
            if requested is not None:
                abort(404)
            return
        if not g.user:
            if requested is not None:
                if request.accept_mimetypes.best == 'application/json':
                    return {'error': 'Please sign in to access your account.'}, 401
                return redirect(url_for('auth.login'))
            return
        if g.account_session['recovery']:
            return redirect(url_for('auth.password'))
        username = current_username()
        if requested is not None:
            if not username or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{2,23}', requested):
                abort(404)
            if not get_db().execute('SELECT 1 FROM profile_usernames WHERE username = ? AND owner_id = ?',
                                    (requested.lower(), g.user['id'])).fetchone():
                abort(404)
        if username and request.method in ('GET', 'HEAD') and request.endpoint == 'auth.profile_overview':
            return redirect(url_for('profiles.public_profile', username=username), code=302)
        if username and request.method in ('GET', 'HEAD') and request.endpoint == 'profiles.sharing':
            return redirect(url_for('auth.profile', _anchor='profile-privacy'), code=302)

    @app.after_request
    def canonical_legacy_get(response):
        if (request.method not in ('GET', 'HEAD') or response.status_code != 200
                or request.endpoint not in {*ALIASES, *ACCOUNT_PAGES}
                or request.endpoint in ('explore.game', 'profiles.public_profile')
                or request.accept_mimetypes.best == 'application/json'):
            return response
        target = url_for(request.endpoint, **(request.view_args or {}))
        if request.path == target:
            return response
        if request.query_string:
            target += '?' + request.query_string.decode('ascii', errors='replace')
        result = redirect(target, code=302)
        result.headers['Cache-Control'] = 'private, no-store'
        return result
