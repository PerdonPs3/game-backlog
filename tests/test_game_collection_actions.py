from html.parser import HTMLParser

from app.db import get_db
from tests.test_accounts import ALICE, accounts, sign_in
from tests.test_public_catalog import fake_catalog


class CollectionLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}
        self.href = None
        self.label = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = ''

    def handle_data(self, data):
        if self.href:
            self.label += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links[self.label.strip()] = self.href
            self.href = None


def test_detail_only_opens_collection_forms_and_preserves_selected_game_and_return_context(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    page = client.get('/games/123/portal-2?from=/discover?mode=popular')
    links = CollectionLinks(); links.feed(page.text)
    assert page.status_code == 200 and 'Add to library' in links.links
    assert '<select' not in page.text and 'name="rating"' not in page.text
    assert 'data-quick-add' not in page.text and 'More options' not in page.text
    assert page.text.count('class="catalog-wishlist-form"') == 1
    form = client.get(links.links['Add to library'], follow_redirects=True)
    assert form.status_code == 200 and 'name="platform"' in form.text and 'name="rating"' in form.text
    assert 'value="Portal 2"' in form.text and 'value="123"' in form.text
    assert '/games/123/portal-2' in form.request.args['from']
    with accounts.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM games').fetchone()[0] == 0


def test_saved_entry_is_read_only_and_edit_prefills_every_saved_field(accounts):
    fake_catalog(accounts)
    client = sign_in(accounts, 'alice')
    with accounts.app_context():
        row = get_db().execute("INSERT INTO games(title,platform,status,rating,review,igdb_id,owner_id) VALUES('Portal 2','PC','Playing',9,'PRIVATE NOTES',123,?) RETURNING id", (ALICE,)).fetchone()
        entry_id = row[0]
    page = client.get('/games/123/portal-2')
    links = CollectionLinks(); links.feed(page.text)
    assert page.text.count('>Edit entry</a>') == 1
    assert 'Add another platform' in links.links and 'Add to library' not in links.links
    assert '<select' not in page.text and 'name="rating"' not in page.text
    assert 'Your rating: 4.5/5' in page.text and 'PRIVATE NOTES' in page.text
    edit = client.get(links.links['Edit entry'])
    assert edit.status_code == 200 and str(entry_id) in edit.request.path
    assert 'PRIVATE NOTES' in edit.text and '4.5 out of 5 stars" checked' in edit.text
    assert 'Remove from library' in edit.text
    assert '/games/123/portal-2' in edit.request.args['from']


def test_anonymous_detail_cannot_expose_private_entries_or_edit_links(accounts):
    fake_catalog(accounts)
    page = accounts.test_client().get('/games/123/portal-2')
    assert 'Sign in to add game' in page.text
    assert '<select' not in page.text and 'name="rating"' not in page.text
    assert 'Edit entry' not in page.text and 'id="your-progress"' not in page.text
