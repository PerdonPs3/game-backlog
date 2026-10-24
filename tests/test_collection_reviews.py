"""Long personal reviews can be expanded without losing or exposing markup."""


def test_long_reviews_are_escaped_and_expandable_in_collection(client, seed_game, stored_games):
    review = 'A long review. ' * 70 + '<script>alert(1)</script>'
    game_id = seed_game(review=review)
    before = stored_games()
    response = client.get('/library', headers={'Accept': 'application/json'})
    page = response.json['html']
    assert '<details class="collection-review">' in page
    assert 'Read more' in page and 'Show less' in page
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page and '<script>alert(1)' not in page
    assert stored_games() == before
    full = client.get(f'/games/{game_id}').get_data(as_text=True)
    assert 'A long review. ' * 70 in full


def test_short_reviews_remain_visible_without_expansion(client, seed_game):
    seed_game(review='A short review.')
    page = client.get('/library', headers={'Accept': 'application/json'}).json['html']
    assert '<p class="game-review">A short review.</p>' in page
    assert 'collection-review' not in page
