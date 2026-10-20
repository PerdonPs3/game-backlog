import json
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError, URLError

import pytest

from app import create_app
from app.auth import AuthError, NoRedirects, SupabaseAuth, token_fields, verified_user


@pytest.fixture
def auth_context():
    application = create_app({"TESTING": True, "SECRET_KEY": "provider-test-only", "AUTH_ENABLED": False,
                              "DATABASE_URL": "postgresql://unused.invalid/test",
                              "SUPABASE_URL": "https://auth.example.invalid", "SUPABASE_PUBLISHABLE_KEY": "public-test-key"})
    with application.app_context():
        yield application


def test_http_contract_keeps_credentials_in_body_and_authorization_header(auth_context, monkeypatch):
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.read.return_value = b'{"ok":true}'
    monkeypatch.setattr("app.auth.build_opener", lambda *args: opener)
    assert SupabaseAuth().call("token?grant_type=password", {"password": "test-password"}) == {"ok": True}
    req = opener.open.call_args.args[0]
    assert req.full_url == "https://auth.example.invalid/auth/v1/token?grant_type=password"
    assert req.method == "POST" and json.loads(req.data)["password"] == "test-password"
    assert req.get_header("Apikey") == "public-test-key"
    SupabaseAuth().call("user", {"password": "new-test-password"}, token="test-access", method="PUT")
    req = opener.open.call_args.args[0]
    assert req.method == "PUT" and req.get_header("Authorization") == "Bearer test-access"
    assert opener.open.call_args.kwargs["timeout"] == 10


@pytest.mark.parametrize("error,unavailable", [
    (HTTPError("https://auth.example.invalid", 401, "test", {}, None), False),
    (HTTPError("https://auth.example.invalid", 429, "test", {}, None), True),
    (HTTPError("https://auth.example.invalid", 503, "test", {}, None), True),
    (URLError("offline"), True),
])
def test_provider_failures_are_sanitized(auth_context, monkeypatch, error, unavailable):
    opener = MagicMock()
    opener.open.side_effect = error
    monkeypatch.setattr("app.auth.build_opener", lambda *args: opener)
    with pytest.raises(AuthError) as result:
        SupabaseAuth().call("user", token="test-access")
    assert result.value.unavailable is unavailable
    assert "test-access" not in str(result.value)


@pytest.mark.parametrize("raw", [b"invalid", b"[]", b"null"])
def test_invalid_provider_response_fails_closed(auth_context, monkeypatch, raw):
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.read.return_value = raw
    monkeypatch.setattr("app.auth.build_opener", lambda *args: opener)
    with pytest.raises(AuthError):
        SupabaseAuth().call("user", token="test-access")


def test_provider_redirects_cannot_forward_credentials():
    assert NoRedirects().redirect_request(None, None, 302, "test", {}, "https://other.invalid") is None


@pytest.mark.parametrize("user", [{}, {"id": 123}, {"id": "invalid"}, {"id": "11111111-1111-4111-8111-111111111111"}])
def test_identity_must_have_valid_uuid_and_confirmed_email(auth_context, user):
    auth_context.extensions["supabase_auth"] = Mock(call=Mock(return_value=user))
    with pytest.raises(AuthError):
        verified_user("test-access")


@pytest.mark.parametrize("payload", [{}, {"access_token": "a", "refresh_token": "r", "expires_in": -1}, {"access_token": "a", "refresh_token": "r", "expires_in": True}])
def test_invalid_token_payload_cannot_create_session(payload):
    with pytest.raises(AuthError):
        token_fields(payload)


@pytest.mark.parametrize("url", ["", "http://auth.example.invalid", "https://user:password@auth.example.invalid", "https://auth.example.invalid/path", "https://auth.example.invalid?secret=test"])
def test_accounts_reject_missing_or_unsafe_auth_urls(url):
    with pytest.raises(ValueError, match="Accounts require"):
        create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE_URL": "postgresql://unused.invalid/test", "AUTH_ENABLED": True, "SUPABASE_URL": url, "SUPABASE_PUBLISHABLE_KEY": "public-test-key"})
