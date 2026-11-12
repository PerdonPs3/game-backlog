from unittest.mock import Mock
from urllib.error import URLError

import pytest

from scripts.check_service_health import check


def response(body=b'{"count": 3}', status=200):
    value = Mock()
    value.__enter__ = Mock(return_value=value)
    value.__exit__ = Mock(return_value=False)
    value.status = status
    value.read.return_value = body
    return value


def test_readiness_requires_a_real_database_backed_signal(app):
    opener = Mock()
    opener.open.return_value = response()
    assert check('https://app.example', opener=opener)
    request = opener.open.call_args.args[0]
    assert request.full_url == 'https://app.example/community/member-count'
    from flask import url_for
    with app.test_request_context():
        assert request.full_url.endswith(url_for('community.count'))
    assert request.get_method() == 'GET'
    assert 'Authorization' not in request.headers
    opener.open.return_value.read.assert_called_with(4096)


@pytest.mark.parametrize('body,status', [(b'{"count":null}',503),(b'{"count":true}',200),
    (b'<html>Sign in</html>',200),(b'{"count":-1}',200),(b'{"status":"ok"}',200),
    (b'{"count":3}',302)])
def test_static_pages_redirects_and_invalid_signals_never_pass(body, status):
    opener = Mock()
    opener.open.return_value = response(body,status)
    sleep = Mock()
    assert not check('https://app.example', opener=opener, sleep=sleep)
    assert opener.open.call_count == 3 and sleep.call_count == 2


def test_temporary_failure_retries_then_recovers():
    opener = Mock()
    opener.open.side_effect = [URLError('offline'),response(b'{"count":0}')]
    sleep = Mock()
    assert check('https://app.example',opener=opener,sleep=sleep)
    assert opener.open.call_count == 2 and sleep.call_count == 1


@pytest.mark.parametrize('url', ['http://app.example','https://user:secret@app.example',
    'https://app.example/path','https://app.example?q=secret','https://app.example#fragment'])
def test_invalid_origins_never_send_a_request(url):
    opener = Mock()
    with pytest.raises(ValueError):
        check(url, opener=opener)
    opener.open.assert_not_called()
