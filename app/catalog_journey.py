"""Carry only a bounded catalog ID through sign-in, never an arbitrary return URL."""

from time import time
from flask import session


SELECTION_SECONDS = 30 * 60


def pending_selection():
    selected = session.get('catalog_selection')
    if (isinstance(selected, dict) and type(selected.get('id')) is int
            and 0 < selected['id'] < 2**63 and type(selected.get('at')) is int
            and 0 <= time() - selected['at'] <= SELECTION_SECONDS):
        return selected
    session.pop('catalog_selection', None)
    return None


def remember_selection(catalog_id):
    session['catalog_selection'] = {'id': catalog_id, 'at': int(time())}


def take_selection():
    selected = pending_selection()
    session.pop('catalog_selection', None)
    return selected['id'] if selected else None


def clear_auth_keep_selection():
    selected = pending_selection()
    session.clear()
    if selected:
        session['catalog_selection'] = selected
