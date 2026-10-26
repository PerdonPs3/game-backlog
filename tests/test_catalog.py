import io
import json
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
from urllib.request import Request

import pytest

from app import catalog


TOKEN = {"access_token": "fake-test-token", "expires_in": 3600}
GAME = {"id": 123, "name": "Resident Evil", "cover": {"image_id": "example"}}


@pytest.fixture(autouse=True)
def block_real_catalog_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Catalog tests must never make real network requests.")
    monkeypatch.setattr(catalog, "urlopen", blocked)


def test_search_uses_server_headers_and_post_body(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, [GAME]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    assert client.search_games("Resident") == [GAME]
    auth_request = request_json.call_args_list[0].args[0]
    assert auth_request.full_url == "https://id.twitch.tv/oauth2/token"
    assert "fake-secret" not in auth_request.full_url
    assert parse_qs(auth_request.data.decode())["client_secret"] == ["fake-secret"]
    search_request = request_json.call_args_list[1].args[0]
    assert search_request.full_url == "https://api.igdb.com/v4/games"
    assert search_request.get_header("Authorization") == "Bearer fake-test-token"
    assert search_request.get_header("Client-id") == "fake-id"
    assert 'name ~ *"Resident"*' in search_request.data.decode()
    assert "cover.image_id" in search_request.data.decode()


def test_access_token_is_reused_until_expiry(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, [GAME], [GAME], TOKEN, [GAME]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    clock = Mock(return_value=100)
    monkeypatch.setattr(catalog, "monotonic", clock)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    client.search_games("Resident")
    client.search_games("Portal")
    assert request_json.call_count == 3
    clock.return_value = 4000
    client.search_games("Resident")
    assert request_json.call_count == 5


def test_unauthorized_search_refreshes_token_once(monkeypatch):
    request_json = Mock(side_effect=[
        TOKEN, catalog.CatalogError("Unauthorized", status=401), TOKEN, [GAME],
    ])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    assert catalog.IGDBClient("fake-id", "fake-secret").search_games("Resident") == [GAME]
    assert request_json.call_count == 4


@pytest.mark.parametrize("term", ["", " ", "r"])
def test_short_search_does_not_request_token(term):
    assert catalog.IGDBClient("fake-id", "fake-secret").search_games(term) == []


def test_overlong_search_is_rejected_without_network():
    with pytest.raises(catalog.CatalogError, match="200 characters"):
        catalog.IGDBClient("fake-id", "fake-secret").search_games("x" * 201)


def test_query_quotes_are_escaped(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, []])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    term = 'Game"; limit 500; search "'
    catalog.IGDBClient("fake-id", "fake-secret").search_games(term)
    body = request_json.call_args.args[0].data.decode()
    assert 'name ~ *"Game"*' in body
    assert 'search "' not in body
    assert body.count(';') == 4
    assert body.endswith("limit 500;")


@pytest.mark.parametrize("payload", [{}, {"access_token": "bad"}, []])
def test_malformed_auth_response_is_rejected(monkeypatch, payload):
    monkeypatch.setattr(catalog, "_request_json", Mock(return_value=payload))
    with pytest.raises(catalog.CatalogError, match="authentication response"):
        catalog.IGDBClient("fake-id", "fake-secret").search_games("Resident")


@pytest.mark.parametrize("payload", [{"error": "bad"}, [{"name": "No ID"}], [None]])
def test_malformed_game_response_is_rejected(monkeypatch, payload):
    monkeypatch.setattr(catalog, "_request_json", Mock(side_effect=[TOKEN, payload]))
    with pytest.raises(catalog.CatalogError, match="game data"):
        catalog.IGDBClient("fake-id", "fake-secret").search_games("Resident")


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_http_errors_do_not_expose_upstream_content(monkeypatch, status):
    error = HTTPError("https://api.igdb.com/v4/games", status, "fake-secret", {}, None)
    monkeypatch.setattr(catalog, "urlopen", Mock(side_effect=error))
    with pytest.raises(catalog.CatalogError) as caught:
        catalog._request_json(Request("https://api.igdb.com/v4/games"))
    assert "fake-secret" not in str(caught.value)
    assert caught.value.status == status


def test_connection_failure_has_safe_message(monkeypatch):
    monkeypatch.setattr(catalog, "urlopen", Mock(side_effect=URLError("fake-secret")))
    with pytest.raises(catalog.CatalogError, match="Could not reach") as caught:
        catalog._request_json(Request("https://api.igdb.com/v4/games"))
    assert "fake-secret" not in str(caught.value)


def test_json_response_is_decoded(monkeypatch):
    opener = Mock(return_value=io.BytesIO(json.dumps([GAME]).encode()))
    monkeypatch.setattr(catalog, "urlopen", opener)
    assert catalog._request_json(Request("https://api.igdb.com/v4/games")) == [GAME]
    assert opener.call_args.kwargs["timeout"] == 10


def test_check_command_without_credentials_is_safe(app):
    result = app.test_cli_runner().invoke(args=["check-igdb"])
    assert result.exit_code != 0
    assert "IGDB_CLIENT_ID" in result.output


def test_check_command_with_mock_catalog(app, monkeypatch):
    app.config.update(IGDB_CLIENT_ID="fake-id", IGDB_CLIENT_SECRET="fake-secret")
    monkeypatch.setattr(catalog, "_request_json", Mock(side_effect=[TOKEN, [GAME]]))
    result = app.test_cli_runner().invoke(args=["check-igdb"])
    assert result.exit_code == 0, result.output
    assert "IGDB connection successful" in result.output
    assert "Resident Evil" in result.output
    assert "fake-secret" not in result.output
    assert "fake-test-token" not in result.output


def test_search_cache_reuses_case_insensitive_results(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, [GAME]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    assert client.search_games("Resident") == client.search_games(" resident ")
    assert request_json.call_count == 2


def test_search_excludes_packs(monkeypatch):
    bundle = {"id": 456, "name": "Resident bundle", "game_type": {"type": "Bundle"}}
    pack = {"id": 789, "name": "Resident pack", "game_type": {"type": "pack"}}
    request_json = Mock(side_effect=[TOKEN, [GAME, bundle, pack]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    assert catalog.IGDBClient("fake-id", "fake-secret").search_games("Resident") == [GAME]
    assert 'game_type.type !=' in request_json.call_args.args[0].data.decode()


def test_suggestion_normalizes_public_metadata():
    result = catalog.game_suggestion({
        **GAME, "first_release_date": 946684800,
        "platforms": [{"id": 6, "name": "PC"}, None, {}],
        "private_extra": "not-for-browser",
    })
    assert result == {
        "id": 123, "name": "Resident Evil", "year": 2000,
        "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_small/example.jpg",
        "platforms": ["PC"],
    }


@pytest.mark.parametrize("cover", [None, {}, {"image_id": "../../evil"}, {"image_id": "https://evil"}])
def test_suggestion_handles_missing_or_unsafe_cover(cover):
    result = catalog.game_suggestion({**GAME, "cover": cover, "platforms": None})
    assert result["cover_url"] is None
    assert result["platforms"] == []
    assert result["year"] is None


def test_catalog_endpoint_returns_suggestions(client, app, stored_games):
    fake_client = Mock()
    fake_client.search_games.return_value = [GAME]
    app.extensions["igdb_client"] = fake_client
    response = client.get("/catalog/search?q=Portal")
    assert response.status_code == 200
    assert response.json["games"][0]["id"] == 123
    fake_client.search_games.assert_called_once_with("Portal", include_community=False, suggestions=True)
    assert stored_games() == []


@pytest.mark.parametrize("term, status", [("", 200), ("r", 200), ("x" * 201, 400)])
def test_catalog_endpoint_validates_query_without_network(client, term, status):
    assert client.get("/catalog/search", query_string={"q": term}).status_code == status


def test_catalog_endpoint_hides_configuration_errors(client):
    response = client.get("/catalog/search?q=Portal")
    assert response.status_code == 503
    assert "IGDB_CLIENT_SECRET" not in response.get_data(as_text=True)


def test_add_form_has_accessible_catalog_picker(client):
    response = client.get("/games/new")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'role="combobox"' in page
    assert 'role="listbox"' in page
    assert '/static/catalog-search.js' in page

def test_community_filter_excludes_provider_tags_and_keeps_independent_games(monkeypatch):
    mod = {'id': 10, 'name': 'Zelda mod', 'game_type': {'type': 'Mod'}}
    fan = {'id': 11, 'name': 'Zelda fan', 'game_type': {'type': 'Main Game'}, 'keywords': [{'name': 'zelda fangame'}]}
    hack = {'id': 12, 'name': 'Zelda hack', 'keywords': [{'name': 'rom hack'}]}
    official = {'id': 7346, 'name': 'The Legend of Zelda: Breath of the Wild', 'total_rating_count': 10000}
    indie = {'id': 13, 'name': 'Independent adventure', 'game_type': {'type': 'Main Game'}}
    request_json = Mock(side_effect=[TOKEN, [mod, fan, hack, official, indie], [mod, fan, hack, official, indie]])
    monkeypatch.setattr(catalog, '_request_json', request_json)
    client = catalog.IGDBClient('fake-id', 'fake-secret')
    assert {g['id'] for g in client.search_games('zelda')} == {7346, 13}
    assert {g['id'] for g in client.search_games('zelda', include_community=True)} == {10, 11, 12, 7346, 13}
    assert request_json.call_count == 3
    client.search_games('ZELDA')
    assert request_json.call_count == 3


def test_series_search_keeps_popular_games_ahead_of_recent_obscure_matches(monkeypatch):
    popular = {'id': 7346, 'name': 'The Legend of Zelda: Breath of the Wild', 'total_rating_count': 10000, 'first_release_date': 1488499200}
    newer = {'id': 20, 'name': 'The Legend of Zelda: Example', 'first_release_date': 1800000000}
    monkeypatch.setattr(catalog, '_request_json', Mock(side_effect=[TOKEN, [newer, popular]]))
    client = catalog.IGDBClient('fake-id', 'fake-secret')
    assert client.search_games('zelda')[0]['id'] == 7346
    assert catalog.search_sort_key(newer, newer['name']) < catalog.search_sort_key(popular, newer['name'])


def test_multiword_search_does_not_require_contiguous_title_words(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, [GAME]])
    monkeypatch.setattr(catalog, '_request_json', request_json)
    catalog.IGDBClient('fake-id', 'fake-secret').search_games('breath of wild')
    body = request_json.call_args.args[0].data.decode()
    for word in ('breath', 'of', 'wild'):
        assert f'name ~ *"{word}"*' in body
        assert f'alternative_names.name ~ *"{word}"*' in body


def test_suggestions_use_bounded_indexed_search_and_keep_aliases(monkeypatch):
    alias = {"id": 9, "name": "Five Nights at Freddy's", "alternative_names": [{"name": "FNAF"}]}
    unrelated = {"id": 10, "name": "Fuzzy match"}
    community = {"id": 11, "name": "FNAF Fan Game", "keywords": [{"name": "fan game"}]}
    request_json = Mock(side_effect=[TOKEN, [unrelated, alias, community]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    assert client.search_games("fnaf", suggestions=True) == [alias]
    query = request_json.call_args.args[0].data.decode()
    assert 'search "fnaf";' in query
    assert 'limit 40;' in query
    assert 'alternative_names.name' in query
    assert 'platforms' not in query
    assert client.search_games("FNAF", suggestions=True) == [alias]
    assert request_json.call_count == 2


def test_suggestions_fall_back_for_uncommon_aliases_and_do_not_replace_full_search(monkeypatch):
    game = {"id": 7, "name": "Rare title"}
    request_json = Mock(side_effect=[TOKEN, [], [game], [game]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    assert client.search_games("alias", suggestions=True) == [game]
    assert 'alternative_names.name ~ *"alias"*' in request_json.call_args.args[0].data.decode()
    assert client.search_games("alias") == [game]
    assert request_json.call_count == 4
    assert 'limit 500;' in request_json.call_args.args[0].data.decode()


def test_suggestions_can_include_community_games(monkeypatch):
    game = {"id": 7, "name": "Portal mod", "game_type": {"type": "Mod"}}
    request_json = Mock(side_effect=[TOKEN, [game]])
    monkeypatch.setattr(catalog, "_request_json", request_json)
    assert catalog.IGDBClient("fake-id", "fake-secret").search_games(
        "Portal", include_community=True, suggestions=True
    ) == [game]


def test_suggestion_cache_reuses_results_for_five_minutes_without_extending_full_search(monkeypatch):
    request_json = Mock(side_effect=[TOKEN, [GAME], [GAME], [GAME], [GAME]])
    clock = Mock(return_value=100)
    monkeypatch.setattr(catalog, "_request_json", request_json)
    monkeypatch.setattr(catalog, "monotonic", clock)
    client = catalog.IGDBClient("fake-id", "fake-secret")
    client.search_games("Resident", suggestions=True)
    clock.return_value = 101
    client.search_games("Resident")
    clock.return_value = 132
    client.search_games("Resident", suggestions=True)
    assert request_json.call_count == 3
    client.search_games("Resident")
    assert request_json.call_count == 4
    clock.return_value = 401
    client.search_games("Resident", suggestions=True)
    assert request_json.call_count == 5
