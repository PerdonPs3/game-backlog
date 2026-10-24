from html.parser import HTMLParser
from pathlib import Path

import pytest


class WorkspaceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("page", ["create", "edit", "delete", "import", "pick"])
def test_secondary_pages_share_design_accessible_heading_and_navigation(client, seed_game, page):
    game_id = seed_game()
    routes = {"create": "/games/new", "edit": f"/games/{game_id}/edit",
              "delete": f"/games/{game_id}/delete", "import": "/backups/import", "pick": "/games/pick"}
    response = client.get(routes[page])
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = WorkspaceParser()
    parser.feed(html)
    assert sum(tag == "h1" for tag, _ in parser.tags) == 1
    assert sum(tag == "main" for tag, _ in parser.tags) == 1
    assert 'class="library-page workspace-page"' in html
    assert 'class="workspace-hero"' in html
    assert 'aria-label="Site navigation"' in html
    assert 'class="hero-emblem" data-hero-logo aria-hidden="true"' in html
    assert "cursor-glow.js" in html
    assert "Back to collection" in html
    if page != "pick":
        assert 'name="csrf_token"' in html


def test_styled_create_form_preserves_catalog_and_review_constraints(client):
    page = client.get("/games/new").get_data(as_text=True)
    assert 'class="workspace-form"' in page
    assert 'role="combobox"' in page
    assert 'id="review"' in page
    assert 'maxlength="2000"' in page
    assert "catalog-search.js" in page


def test_styled_import_preserves_upload_and_confirmation_controls(client):
    page = client.get("/backups/import").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in page
    assert 'name="confirm_import" value="yes" required' in page
    assert "never overwritten" in page


def test_primary_button_theme_does_not_target_catalog_suggestions():
    stylesheet = (Path(__file__).parents[1] / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".workspace-form button," not in stylesheet
    assert ".workspace-form .form-actions > button," in stylesheet
