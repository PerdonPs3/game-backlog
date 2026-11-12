"""Carry a bounded catalog selection and validated local context through sign-in."""

from time import time
from flask import session, request


SELECTION_SECONDS = 30 * 60


def pending_selection():
    selected = session.get('catalog_selection')
    if (isinstance(selected, dict) and type(selected.get('id')) is int
            and 0 < selected['id'] < 2**63 and type(selected.get('at')) is int
            and 0 <= time() - selected['at'] <= SELECTION_SECONDS
            and selected.get('intent', 'library') in ('library', 'wishlist')):
        return selected
    session.pop('catalog_selection', None)
    return None


def remember_selection(catalog_id, *, intent='library'):
    session['catalog_selection'] = {'id': catalog_id, 'at': int(time())}
    from app.navigation import safe_destination
    origin = safe_destination(request.args.get('from'))
    if origin:
        session['catalog_selection']['return_path'] = origin
    if intent == 'wishlist':
        session['catalog_selection']['intent'] = 'wishlist'


def take_selection():
    selected = pending_selection()
    session.pop('catalog_selection', None)
    return selected['id'] if selected else None


def clear_auth_keep_selection():
    selected = pending_selection()
    from app.navigation import pending_login_destination
    target = pending_login_destination()
    session.clear()
    if selected:
        session['catalog_selection'] = selected
    if target:
        session['navigation_login'] = {'path': target, 'at': int(time())}
