from html.parser import HTMLParser

import pytest

from app import create_app
from app.db import get_db


class CSRFTokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "csrf_token":
            self.token = attributes.get("value")


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-not-for-deployment",
        "DATABASE": str(tmp_path / "test.sqlite"),
    })
    result = application.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def post_form(client):
    """Submit with a real CSRF token, keeping protection enabled."""
    def submit(url, data):
        page = client.get(url)
        assert page.status_code == 200
        parser = CSRFTokenParser()
        parser.feed(page.get_data(as_text=True))
        assert parser.token is not None
        return client.post(url, data={**data, "csrf_token": parser.token})

    return submit


@pytest.fixture
def game_data():
    return {
        "title": "Portal 2", "platform": "PC", "status": "Playing",
        "rating": "9", "review": "A great puzzle game.",
    }


@pytest.fixture
def seed_game(app, game_data):
    """Insert games into this test's temporary database only."""
    def insert(**overrides):
        data = {**game_data, **overrides}
        with app.app_context():
            db = get_db()
            cursor = db.execute(
                "INSERT INTO games (title, platform, status, rating, review) "
                "VALUES (?, ?, ?, ?, ?)",
                (data["title"], data["platform"], data["status"],
                 data["rating"], data["review"]),
            )
            db.commit()
            return cursor.lastrowid

    return insert


@pytest.fixture
def stored_games(app):
    def read():
        with app.app_context():
            rows = get_db().execute("SELECT * FROM games ORDER BY id").fetchall()
            return [dict(row) for row in rows]

    return read
