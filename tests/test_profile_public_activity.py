"""Default public statistics, bounded activity, owner controls, and long reviews."""
import re

import pytest

from app.db import get_db
from tests.test_accounts import ALICE, BOB, accounts, sign_in, submit
from tests.test_game_reviews import public_author
from tests.test_community_profiles import add_review
from tests.test_public_catalog import fake_catalog


def populate(app):
    alice = public_author(app, 'alice')
    sign_in(app, 'bob')
    with app.app_context():
        db = get_db()
        for index in range(4):
            db.execute("INSERT INTO games (owner_id,title,platform,status,rating,review,igdb_id,started_on) VALUES (?,?,'PC','Playing',8,'PRIVATE ACTIVITY NOTE',?,?)", (ALICE, f'ALICE PLAY {index}', 100+index, f'2026-10-{index+1:02d}'))
            db.execute("INSERT INTO games (owner_id,title,platform,status,rating,review,igdb_id,completed_on) VALUES (?,?,'PC','Completed',9,'PRIVATE COMPLETION NOTE',?,?)", (ALICE, f'ALICE DONE {index}', 200+index, f'2026-10-{index+1:02d}'))
        for title,status,owner in [('HIDDEN BACKLOG','Backlog',ALICE),('SECOND BACKLOG','Backlog',ALICE),('UNDATED FINISH','Completed',ALICE),('BOB FOREIGN','Playing',BOB),('UNOWNED LEGACY','Playing',None)]:
            db.execute("INSERT INTO games (owner_id,title,platform,status) VALUES (?,?,'PC',?)", (owner,title,status))
    return alice


def test_public_defaults_include_only_aggregate_and_three_activity_rows(accounts):
    populate(accounts)
    response = accounts.test_client().get('/players/alice_player')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'aria-label="Public gaming statistics"' in html and '<dd>11</dd>' in html
    assert '<dd>5</dd>' in html and '<dd>4</dd>' in html and '<dd>45<small>%</small></dd>' in html
    for label in ['ALICE PLAY 3','ALICE PLAY 2','ALICE PLAY 1','ALICE DONE 3','ALICE DONE 2','ALICE DONE 1','2026-10-04']:
        assert label in html
    assert '/games/103/alice-play-3' in html
    for private in ['ALICE PLAY 0','ALICE DONE 0','HIDDEN BACKLOG','SECOND BACKLOG','UNDATED FINISH','BOB FOREIGN','UNOWNED LEGACY','PRIVATE ACTIVITY NOTE','PRIVATE COMPLETION NOTE',ALICE,BOB,'alice@example.test','href="/library/entries/']:
        assert private not in html
    assert response.headers['Cache-Control'] == 'private, no-store'


def test_sections_can_be_hidden_independently_in_editor_and_choices_survive_old_forms(accounts):
    alice = populate(accounts)
    editor = alice.get('/settings/profile').get_data(as_text=True)
    for field in ['share_statistics','share_activity']:
        assert re.search(r'<input[^>]*name="'+field+r'"[^>]*checked', editor)
    data = {'display_name':'Alice','username':'alice_player','is_public':'yes','profile_sharing':'yes','profile_activity_controls':'yes'}
    assert submit(alice,'/account/alice_player/profile/edit',{**data,'share_statistics':'yes'}).status_code == 303
    anon = accounts.test_client()
    html = anon.get('/players/alice_player').get_data(as_text=True)
    assert 'Public gaming statistics' in html and 'ALICE PLAY 3' not in html and 'Recent completions' not in html
    assert submit(alice,'/account/alice_player/profile/edit',{**data,'share_activity':'yes'}).status_code == 303
    html = anon.get('/players/alice_player').get_data(as_text=True)
    assert 'Public gaming statistics' not in html and 'Average rating' not in html and 'ALICE PLAY 3' in html
    assert submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'yes'}).status_code == 303
    with accounts.app_context():
        assert tuple(get_db().execute('SELECT share_statistics,share_activity FROM profiles WHERE id=?',(ALICE,)).fetchone()) == (False,True)
    assert submit(alice,'/account/alice_player/profile/edit',data).status_code == 303
    html = anon.get('/players/alice_player').get_data(as_text=True)
    assert 'Public gaming statistics' not in html and 'ALICE PLAY 3' not in html
    # Hiding a public section never removes it from the owner's workspace.
    assert b'ALICE PLAY 3' in alice.get('/players/alice_player').data


def test_private_profile_revokes_activity_and_legacy_games_never_link_to_private_entries(accounts):
    alice = public_author(accounts,'alice')
    with accounts.app_context():
        get_db().execute("INSERT INTO games (title,platform,status,owner_id) VALUES ('Legacy playing','PC','Playing',?)",(ALICE,))
    html = accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert 'Legacy playing' in html and '<div class="profile-activity-item">' in html
    assert 'href="/library/entries/' not in html
    submit(alice,'/account/profile/sharing',{'username':'alice_player','is_public':'no'})
    assert accounts.test_client().get('/players/alice_player').status_code == 404
    assert accounts.test_client().get('/community/players?q=alice').get_data(as_text=True).count('class="player-result"') == 0


def test_editor_validation_does_not_save_settings_and_preserves_submitted_checks(accounts):
    alice = public_author(accounts,'alice')
    response = submit(alice,'/account/alice_player/profile/edit',{'display_name':'','username':'alice_player','is_public':'yes','profile_sharing':'yes','profile_activity_controls':'yes','share_activity':'yes'})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert re.search(r'<input[^>]*name="share_activity"[^>]*checked',html)
    assert not re.search(r'<input[^>]*name="share_statistics"[^>]*checked',html)
    with accounts.app_context():
        assert tuple(get_db().execute('SELECT share_statistics,share_activity FROM profiles WHERE id=?',(ALICE,)).fetchone()) == (True,True)


def test_long_and_multiline_reviews_use_native_disclosures_and_escape_text(accounts):
    fake_catalog(accounts)
    public_author(accounts,'alice')
    body = ('A long published story. ' * 60) + '<script>never()</script>'
    add_review(accounts,body=body)
    html = accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert '<details class="profile-review-expand">' in html and 'Read more' in html and 'Show less' in html
    assert '&lt;script&gt;never()&lt;/script&gt;' in html and '<script>never()' not in html
    assert body.replace('<script>never()</script>','&lt;script&gt;never()&lt;/script&gt;') in html
    # Spoilers must not enter the otherwise visible excerpt.
    with accounts.app_context():
        get_db().execute('UPDATE public_game_reviews SET has_spoilers=TRUE WHERE owner_id=?',(ALICE,))
    html = accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert '<details class="profile-review-spoilers">' in html and 'profile-review-excerpt' not in html


def test_short_reviews_remain_visible_and_blank_line_heavy_text_is_collapsed(accounts):
    fake_catalog(accounts);public_author(accounts,'alice')
    add_review(accounts,body='A short public thought.')
    html = accounts.test_client().get('/players/alice_player').get_data(as_text=True)
    assert '<p>A short public thought.</p>' in html and '<details class="profile-review-expand">' not in html
    with accounts.app_context():
        get_db().execute('UPDATE public_game_reviews SET body=? WHERE owner_id=?',('one\ntwo\nthree\nfour\nfive',ALICE))
    assert b'<details class="profile-review-expand">' in accounts.test_client().get('/players/alice_player').data
