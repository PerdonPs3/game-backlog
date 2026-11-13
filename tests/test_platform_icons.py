from unittest.mock import Mock

import pytest

from app.platform_icons import platform_badges
from app.public_catalog import catalog_card
from tests.test_accounts import ALICE, BOB, accounts, sign_in
from app.db import get_db


def test_platform_families_keep_versions_and_unknown_names_without_duplicates():
    badges = platform_badges(['PC (Microsoft Windows)', 'PlayStation 4', 'PlayStation 5',
                              'Xbox Series X|S', 'Nintendo Switch', 'Dreamcast'])
    assert [badge['icon'] for badge in badges] == ['windows', 'playstation', 'xbox', 'nintendoswitch', None]
    assert badges[1]['title'] == 'PlayStation 4, PlayStation 5'
    assert badges[-1]['label'] == '+1' and badges[-1]['title'] == 'Dreamcast'
    assert platform_badges(['PC', 'PC', 'Linux', 'Mac'])[0]['names'] == ['PC']
    assert platform_badges(['Dreamcast'])[0]['label'] == 'Dreamcast'
    assert platform_badges([]) == []


def test_primary_gaming_platforms_remain_visible_before_extra_operating_systems():
    badges = platform_badges(['Linux', 'Mac', 'PC', 'PlayStation 4', 'Xbox One'],
                             [{'label': 'Steam'}])
    assert [badge['icon'] for badge in badges[:4]] == ['steam', 'windows', 'playstation', 'xbox']
    assert badges[-1]['label'] == '+2' and 'Linux' in badges[-1]['title']


@pytest.mark.parametrize('url,verified', [
    ('https://store.steampowered.com/app/123/Game/', True),
    ('https://store.steampowered.com.evil.test/app/123', False),
    ('http://store.steampowered.com/app/123', False),
])
def test_pc_never_implies_steam_and_only_validated_store_metadata_adds_its_logo(app, url, verified):
    raw = {'id': 123, 'name': 'Game', 'platforms': [{'name': 'PC'}]}
    with app.test_request_context('/discover'):
        assert [item['icon'] for item in catalog_card(raw)['platform_badges']] == ['windows']
        raw['websites'] = [{'type': {'type': 'Steam'}, 'url': url}]
        badges = catalog_card(raw)['platform_badges']
        assert any(item['icon'] == 'steam' for item in badges) is verified


@pytest.mark.parametrize('path', ['/discover', '/discover?mode=popular', '/discover/browse?q=Portal'])
def test_discover_destinations_render_platform_logos_and_read_only_game_cards(app, client, path):
    catalog = Mock()
    games = [{'id': 123, 'name': '<Portal>', 'platforms': [{'id': 6, 'name': 'PC'},
             {'id': 48, 'name': 'PlayStation 4'}, {'id': 49, 'name': 'Xbox One'}]}]
    catalog.get_discovery_games.return_value = games
    catalog.search_games.return_value = games
    app.extensions['igdb_client'] = catalog
    response = client.get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'platform-brand-playstation' in body and 'platform-brand-xbox' in body
    assert 'data-discover-wish=' not in body and 'Add to wishlist' not in body
    assert '&lt;Portal&gt;' in body
    if '/browse' not in path:
        assert 'aria-label="View &lt;Portal&gt;"' in body
        assert body.count('class="discover-card-link"') == 1


def test_search_status_is_owner_scoped_and_does_not_expose_another_players_wishlist(accounts):
    provider = Mock()
    provider.search_games.return_value = [{'id': 123, 'name': 'Portal', 'platforms': [{'id': 6, 'name': 'PC'}]}]
    accounts.extensions['igdb_client'] = provider
    alice, bob = sign_in(accounts, 'alice'), sign_in(accounts, 'bob')
    with accounts.app_context():
        db = get_db()
        db.execute("INSERT INTO games (title,platform,igdb_id,owner_id) VALUES ('Portal','PC',123,?)", (ALICE,))
        db.execute("INSERT INTO wishlist_games (owner_id,catalog_id,title) VALUES (?,123,'Portal')", (BOB,))
    alice_page = alice.get('/discover/browse?q=Portal').get_data(as_text=True)
    bob_page = bob.get('/discover/browse?q=Portal').get_data(as_text=True)
    anonymous = accounts.test_client().get('/discover/browse?q=Portal').get_data(as_text=True)
    assert 'In your library' in alice_page and 'On your wishlist' not in alice_page
    assert 'On your wishlist' in bob_page and 'In your library' not in bob_page
    assert 'In your library' not in anonymous and 'On your wishlist' not in anonymous
