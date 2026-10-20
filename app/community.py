"""Public aggregate of activated player accounts; never expose account records."""

from threading import Lock
from time import monotonic
from uuid import UUID

from flask import Blueprint, current_app, jsonify
from psycopg import Error as DatabaseError

from app.db import get_db

community = Blueprint('community', __name__, url_prefix='/community')


class MemberCount:
    def __init__(self):
        self.lock = Lock()
        self.expires = 0
        self.value = None

    def get(self):
        with self.lock:
            now = monotonic()
            if now < self.expires:
                return self.value
            try:
                excluded = current_app.config.get('PUBLIC_MEMBER_COUNT_EXCLUDED_IDS', '')
                ids = [str(UUID(value.strip())) for value in excluded.split(',') if value.strip()]
                where = ' WHERE id NOT IN (' + ','.join('?' for _ in ids) + ')' if ids else ''
                self.value = int(get_db().execute('SELECT COUNT(*) AS total FROM profiles' + where, ids).fetchone()['total'])
            except (DatabaseError, ValueError, TypeError):
                self.value = None
                current_app.logger.warning('Public member count is temporarily unavailable.')
            self.expires = now + 60
            return self.value


def member_count():
    # SQLite/offline installations have no registered account population.
    if not current_app.config.get('AUTH_ENABLED'):
        return None
    return current_app.extensions.setdefault('member_count', MemberCount()).get()


@community.get('/member-count')
def count():
    value = member_count()
    response = jsonify(count=value)
    response.status_code = 200 if value is not None else 503
    response.headers['Cache-Control'] = 'no-store'
    return response


def init_app(app):
    app.register_blueprint(community)
