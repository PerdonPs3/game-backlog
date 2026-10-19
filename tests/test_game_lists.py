import json

import pytest

from app.db import get_db
from app.backups import BackupError, parse_backup
from tests.test_backups import backup_entry, encoded, import_file


def saved_lists(app):
    with app.app_context():
        db = get_db()
        return [dict(row) for row in db.execute("SELECT * FROM game_lists ORDER BY id")], [tuple(row) for row in db.execute("SELECT list_id, game_id FROM game_list_members ORDER BY list_id, game_id")]


def make_list(post_form, name="Game night"):
    response = post_form("/lists", {"name": name})
    assert response.status_code == 302
    return response.headers["Location"]


def test_create_rename_and_many_to_many_membership(app, client, post_form, seed_game, stored_games):
    first = seed_game(title="Portal 2")
    second = seed_game(title="Another game")
    before = stored_games()
    one = make_list(post_form)
    two = make_list(post_form, "Summer backlog")
    assert post_form(one, {"name": "With friends", "games": [str(first), str(second)]}).status_code == 302
    assert post_form(two, {"name": "Summer backlog", "games": [str(first)]}).status_code == 302
    lists, members = saved_lists(app)
    assert lists[0]["name"] == "With friends"
    assert members == [(lists[0]["id"], first), (lists[0]["id"], second), (lists[1]["id"], first)]
    assert stored_games() == before
    assert b"With friends" in client.get("/lists").data


def test_list_filters_combine_with_search_status_and_json(app, client, post_form, seed_game):
    first = seed_game(title="Portal 2", status="Playing")
    second = seed_game(title="Portal", status="Completed")
    seed_game(title="Not in this list")
    edit = make_list(post_form)
    response = post_form(edit, {"name": "Puzzle", "games": [str(first), str(second)]})
    assert "/edit?" in response.headers["Location"]
    url = f"/?list={saved_lists(app)[0][0]['id']}"
    page = client.get(url + "&q=Portal&status=Playing", headers={"Accept": "application/json"})
    assert page.json["count"] == 1
    assert "Portal 2" in page.json["html"]
    assert "Not in this list" not in page.json["html"]
    assert b'id="list-filter"' in client.get(url).data


def test_remove_memberships_and_delete_list_preserve_games(app, client, post_form, seed_game, stored_games):
    entry = seed_game()
    edit = make_list(post_form)
    post_form(edit, {"name": "Game night", "games": [str(entry)]})
    before = stored_games()
    post_form(edit, {"name": "Game night"})
    assert saved_lists(app)[1] == []
    post_form(edit, {"name": "Game night", "games": [str(entry)]})
    delete = edit.replace("/edit", "/delete")
    assert client.get(delete).status_code == 200
    assert len(saved_lists(app)[0]) == 1
    assert post_form(delete, {}).status_code == 302
    assert saved_lists(app) == ([], [])
    assert stored_games() == before


def test_game_deletion_cleans_links_only(app, post_form, seed_game):
    entry = seed_game()
    edit = make_list(post_form)
    post_form(edit, {"name": "Game night", "games": [str(entry)]})
    post_form(f"/games/{entry}/delete", {})
    lists, members = saved_lists(app)
    assert len(lists) == 1 and members == []


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "bad\nname"])
def test_invalid_names_do_not_create_lists(app, post_form, name):
    assert post_form("/lists", {"name": name}).status_code == 200
    assert saved_lists(app)[0] == []


def test_duplicate_names_and_failed_edits_are_atomic(app, post_form, seed_game):
    entry = seed_game()
    edit = make_list(post_form)
    make_list(post_form, "Other")
    assert b"already exists" in post_form("/lists", {"name": " game NIGHT "}).data
    post_form(edit, {"name": "Game night", "games": [str(entry)]})
    before = saved_lists(app)
    assert b"already exists" in post_form(edit, {"name": "OTHER"}).data
    assert saved_lists(app) == before
    assert b"no longer" in post_form(edit, {"name": "New name", "games": ["999999"]}).data
    assert saved_lists(app) == before
    assert b"choose games" in post_form(edit, {"name": "New name", "games": ["1;drop"]}).data
    assert saved_lists(app) == before


def test_list_routes_require_csrf_and_missing_list_is_404(client):
    assert client.post("/lists", data={"name": "No CSRF"}).status_code == 400
    assert client.post("/lists/1/edit", data={"name": "No CSRF"}).status_code == 400
    assert client.post("/lists/1/delete").status_code == 400
    assert client.get("/lists/999/edit").status_code == 404
    assert client.get("/?list=999").status_code == 404
    assert client.get("/?list=not-an-id").status_code == 400


def test_list_limit_and_foreign_keys(app, post_form):
    with app.app_context():
        db = get_db()
        if not app.config.get("DATABASE_URL"):
            assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.executemany("INSERT INTO game_lists (name, name_key) VALUES (?, ?)", [(f"List {i}", f"list {i}") for i in range(100)])
        db.commit()
    assert b"up to 100" in post_form("/lists", {"name": "Too many"}).data
    assert len(saved_lists(app)[0]) == 100


def test_save_returns_to_editor_with_confirmation_and_selected_view(client, post_form, seed_game):
    entry = seed_game()
    edit = make_list(post_form)
    response = post_form(edit, {"name": "Saved here", "games": [str(entry)], "view": "selected"})
    assert response.status_code == 302
    assert response.headers["Location"] == edit + "?view=selected#list-feedback"
    page = client.get(response.headers["Location"])
    assert b"List saved." in page.data
    assert b'value="selected"' in page.data
    assert b"In this list" in page.data
    assert b"List saved." not in client.get(edit).data


def test_list_cards_preview_covers_and_invalid_name_keeps_draft_choices(app, client, post_form, seed_game):
    entry = seed_game()
    with app.app_context():
        db = get_db()
        db.execute("UPDATE games SET cover_image_id = 'co_example' WHERE id = ?", (entry,))
        db.commit()
    edit = make_list(post_form)
    post_form(edit, {"name": "Game night", "games": [str(entry)]})
    assert b"t_cover_big/co_example.jpg" in client.get("/lists").data
    page = post_form(edit, {"name": "", "games": [str(entry)], "view": "selected"})
    assert b"without control characters" in page.data
    assert f'value="{entry}" checked'.encode() in page.data


def test_names_are_escaped_and_lists_can_be_empty(app, client, post_form):
    make_list(post_form, "<script>list</script>")
    html = client.get("/lists").get_data(as_text=True)
    assert "<script>list</script>" not in html
    assert "&lt;script&gt;" in html
    list_id = saved_lists(app)[0][0]["id"]
    assert b"No games in this list" in client.get(f"/?list={list_id}").data


def test_backup_lists_roundtrip_merges_without_erasing_memberships(app, client, post_form, seed_game, stored_games):
    first = seed_game()
    second = seed_game(title="Other game")
    edit = make_list(post_form)
    post_form(edit, {"name": "Game night", "games": [str(first)]})
    exported = client.get("/backups/export").json
    assert exported["lists"] == [{"name": "Game night", "games": [0]}]
    before = stored_games()
    post_form(edit, {"name": "Game night", "games": [str(second)]})
    assert import_file(client, json.dumps(exported).encode()).status_code == 200
    assert stored_games() == before
    assert len(saved_lists(app)[1]) == 2
    # Restoring into a fresh collection uses backup indices, never old local IDs.
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM game_lists")
        db.execute("DELETE FROM games")
        db.commit()
    import_file(client, json.dumps(exported).encode())
    assert len(saved_lists(app)[0]) == 1 and len(saved_lists(app)[1]) == 1
    assert len(stored_games()) == 2


@pytest.mark.parametrize("lists", [None, [{"name": "Bad", "games": [True]}],
    [{"name": "Bad", "games": [999]}], [{"name": "", "games": []}],
    [{"name": "Same", "games": []}, {"name": "same", "games": []}]])
def test_bad_backup_lists_reject_entire_import(client, backup_entry, stored_games, lists):
    raw = encoded([backup_entry], lists=lists)
    with pytest.raises(BackupError):
        parse_backup(raw)
    import_file(client, raw)
    assert stored_games() == []
