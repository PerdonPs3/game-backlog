from unittest.mock import Mock

import pytest

from app.help_center import TOPICS


def test_help_is_public_and_does_not_query_the_catalog_or_database(app, client, monkeypatch):
    query = Mock(side_effect=AssertionError('Help must not query the database.'))
    monkeypatch.setattr('app.db.get_db', query)
    app.extensions['igdb_client'] = Mock()
    response = client.get('/help')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for _, title, _, entries in TOPICS:
        assert title.replace('&', '&amp;') in html
        for question, _ in entries:
            assert question in html
    assert 'aria-label="Search the game catalog"' not in html
    assert 'href="/help"' not in html
    query.assert_not_called()
    app.extensions['igdb_client'].get_game.assert_not_called()


def test_help_filters_without_javascript_and_keeps_full_content_for_live_search(client):
    html = client.get('/help?q=HALF+STARS').get_data(as_text=True)
    assert 'id="help-reviews" data-help-topic>' in html
    assert 'id="help-wishlist" data-help-topic hidden' in html
    assert 'No answers found' in html
    assert 'data-help-empty role="status" hidden' in html
    empty = client.get('/help?q=zzzzzz').get_data(as_text=True)
    assert 'data-help-empty role="status">' in empty
    assert empty.count('data-help-topic hidden') == len(TOPICS)


@pytest.mark.parametrize('query', ['x'*201, '\x00'])
def test_help_rejects_invalid_queries(client, query):
    assert client.get('/help', query_string={'q': query}).status_code == 400


def test_help_link_appears_once_in_the_shared_footer(client):
    html = client.get('/discover/browse').get_data(as_text=True)
    assert html.count('href="/help"') == 1


def test_add_game_demo_is_local_accessible_and_loaded_only_when_opened(client):
    html = client.get('/help').get_data(as_text=True)
    assert html.count('<video ') == 1
    assert 'controls muted playsinline preload="none"' in html
    assert 'data-src="/static/videos/help-add-game.mp4?v=2"' in html
    assert '30 seconds · No audio' in html
    assert 'kind="captions"' in html and 'data-help-replay hidden' in html
    media = client.get('/static/videos/help-add-game.mp4', headers={'Range': 'bytes=0-99'})
    assert media.status_code == 206 and media.mimetype == 'video/mp4'
    assert len(media.data) == 100
    assert client.get('/static/videos/help-add-game-poster.webp').status_code == 200
    assert client.get('/static/videos/help-add-game.vtt').status_code == 200
