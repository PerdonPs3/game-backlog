from html.parser import HTMLParser


class LibraryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_library_has_single_wordmark_primary_action_and_reusable_emblem(client):
    page = client.get("/library").get_data(as_text=True)
    parser = LibraryParser()
    parser.feed(page)
    assert sum(tag == "h1" for tag, _ in parser.tags) == 1
    assert any(tag == "h1" and attrs.get("class") == "library-wordmark" for tag, attrs in parser.tags)
    assert sum(tag == "a" and attrs.get("href") == "/games/new" for tag, attrs in parser.tags) == 1
    assert page.count('id="brand-symbol"') == 1
    assert '<use href="#brand-symbol"' in page
    assert 'class="hero-emblem" data-hero-logo aria-hidden="true"' in page


def test_dashboard_retains_all_live_controls_and_existing_features(client):
    page = client.get("/library").get_data(as_text=True)
    for element_id in ["collection-summary", "title-search", "status-filter", "collection-sort",
                       "game-collection", "delete-game-dialog"]:
        assert f'id="{element_id}"' in page
    assert 'id="filter-reset" hidden' in page
    assert "cursor-glow.js" in page
    assert "collection-filters.js" in page
    assert "delete-confirmation.js" in page


def test_library_layout_does_not_replace_other_form_layouts(client):
    page = client.get("/games/new").get_data(as_text=True)
    assert "library-hero" not in page
    assert "catalog-picker" in page
