"""Canonical account pages retain session ownership, never URL-based ownership."""

import re

from flask import abort, current_app, g, redirect, request, url_for

from app.db import get_db


ACCOUNT_PAGES = {
    "wishlist.index": ("/account/<username>/wishlist", ["GET"]),
    "main.index": ("/account/<username>/library", ["GET"]),
    "auth.profile_overview": ("/account/<username>/profile", ["GET", "POST"]),
    "auth.profile": ("/account/<username>/profile/edit", ["GET", "POST"]),
    "auth.edit_showcase": ("/account/<username>/profile/showcase", ["GET", "POST"]),
    "profiles.sharing": ("/account/<username>/profile/sharing", ["GET", "POST"]),
}


def current_username():
    profile = getattr(g, "profile", None)
    recovery = (getattr(g, "account_session", None) or {}).get("recovery")
    if getattr(g, "user", None) and profile and profile["display_name"].strip() and not recovery:
        return profile["username"]
    return None


def init_app(app):
    for endpoint, (path, methods) in ACCOUNT_PAGES.items():
        app.add_url_rule(path, endpoint=endpoint, view_func=app.view_functions[endpoint], methods=methods)

    @app.url_value_preprocessor
    def account_path_values(endpoint, values):
        if endpoint in ACCOUNT_PAGES and values is not None:
            # Views continue querying the authenticated owner, without accepting
            # an identity argument from the URL.
            g.account_path_username = values.pop("username", None)

    @app.url_defaults
    def account_link_values(endpoint, values):
        if endpoint == 'profiles.public_profile' and 'username' not in values:
            username = current_username()
            if username:
                values['username'] = username
        if endpoint in ACCOUNT_PAGES and "username" not in values:
            username = current_username()
            if username:
                values["username"] = username

    @app.before_request
    def canonical_account_page():
        if request.endpoint not in ACCOUNT_PAGES:
            return
        requested = getattr(g, "account_path_username", None)
        if not current_app.config.get("AUTH_ENABLED"):
            if requested is not None:
                abort(404)
            return
        if not g.user:
            if requested is not None:
                if request.accept_mimetypes.best == "application/json":
                    return {"error": "Please sign in to access your account."}, 401
                return redirect(url_for("auth.login"))
            return
        if g.account_session["recovery"]:
            return redirect(url_for("auth.password"))
        username = current_username()
        if requested is not None:
            if not username or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{2,23}", requested):
                abort(404)
            if requested.lower() != username:
                alias = get_db().execute(
                    "SELECT 1 FROM profile_usernames WHERE username = ? AND owner_id = ?",
                    (requested.lower(), g.user["id"]),
                ).fetchone()
                if not alias:
                    abort(404)
        # Legacy POSTs still execute once with CSRF protection. Keep the legacy
        # JSON collection endpoint compatible with existing clients as well.
        if username and request.method in ('GET', 'HEAD') and request.endpoint == 'auth.profile_overview':
            return redirect(url_for('profiles.public_profile', username=username), code=302)
        if username and request.method in ('GET', 'HEAD') and request.endpoint == 'profiles.sharing':
            return redirect(url_for('auth.profile', username=username, _anchor='profile-privacy'), code=302)
        if username and request.method in ("GET", "HEAD") and requested != username:
            if requested is None and request.accept_mimetypes.best == "application/json":
                return
            target = url_for(request.endpoint, username=username)
            if request.query_string:
                target += "?" + request.query_string.decode("ascii", errors="replace")
            return redirect(target, code=302)
