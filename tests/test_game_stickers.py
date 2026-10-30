import io
import json
import sqlite3
from pathlib import Path

import pytest

from app import create_app
from app.backups import BackupError, parse_backup
from app.db import get_db
from tests.conftest import CSRFTokenParser


@pytest.mark.parametrize("favorite,goty", [(False, False), (True, False), (False, True), (True, True)])
def test_stickers_are_independent_and_visible(client, post_form, game_data, stored_games, favorite, goty):
    data = {**game_data}
    if favorite:
        data["is_favorite"] = "yes"
    if goty:
        data["is_goty"] = "yes"
    assert post_form("/library/add", data).status_code == 302
    saved = stored_games()[0]
    assert saved["is_favorite"] == int(favorite)
    assert saved["is_goty"] == int(goty)
    for headers in [{}, {"Accept": "application/json"}]:
        page = client.get("/library", headers=headers)
        html = page.json["html"] if page.is_json else page.get_data(as_text=True)
        assert ('class="game-sticker sticker-favorite"' in html) is favorite
        assert ('class="game-sticker sticker-goty"' in html) is goty


def test_edit_can_add_and_remove_stickers(client, post_form, game_data, seed_game, stored_games):
    game_id = seed_game()
    url = f"/library/entries/{game_id}/edit"
    marked = {**game_data, "is_favorite": "yes", "is_goty": "yes"}
    assert post_form(url, marked).status_code == 302
    page = client.get(url).get_data(as_text=True)
    import re
    assert len(re.findall(r'<input[^>]+type="checkbox"[^>]+checked', page)) == 2
    assert stored_games()[0]["is_goty"] == 1
    assert post_form(url, game_data).status_code == 302
    assert stored_games()[0]["is_favorite"] == 0
    assert stored_games()[0]["is_goty"] == 0


def test_invalid_form_keeps_sticker_choices_without_saving(post_form, game_data, stored_games):
    response = post_form("/library/add", {**game_data, "is_favorite": "yes", "is_goty": "yes", "rating": "99"})
    assert response.status_code == 200
    assert response.get_data(as_text=True).count("checked") == 2
    assert stored_games() == []


def test_stickers_round_trip_in_backup_and_old_exports_still_work(client, post_form, game_data, stored_games):
    assert post_form("/library/add", {**game_data, "is_favorite": "yes", "is_goty": "yes"}).status_code == 302
    payload = client.get("/settings/data/export").json
    entry = payload["games"][0]
    assert entry["is_favorite"] is True
    assert entry["is_goty"] is True
    assert parse_backup(json.dumps(payload).encode())[0]["is_goty"] == 1
    entry.pop("is_favorite")
    entry.pop("is_goty")
    restored = parse_backup(json.dumps(payload).encode())[0]
    assert restored["is_favorite"] == 0
    assert restored["is_goty"] == 0


@pytest.mark.parametrize("value", [2, -1, "yes", [], None])
def test_invalid_backup_sticker_values_are_rejected(client, seed_game, value):
    seed_game()
    payload = client.get("/settings/data/export").json
    payload["games"][0]["is_favorite"] = value
    with pytest.raises(BackupError):
        parse_backup(json.dumps(payload).encode())


def test_import_restores_stickers(client, post_form, game_data, stored_games):
    assert post_form("/library/add", game_data).status_code == 302
    payload = client.get("/settings/data/export").json
    payload["games"][0].update(igdb_id=456, title="Another game", is_favorite=True, is_goty=True)
    parser = CSRFTokenParser()
    parser.feed(client.get("/settings/data/import").get_data(as_text=True))
    response = client.post("/settings/data/import", data={
        "csrf_token": parser.token, "confirm_import": "yes",
        "backup": (io.BytesIO(json.dumps(payload).encode()), "backup.json"),
    })
    assert response.status_code == 200
    assert stored_games()[1]["is_favorite"] == 1
    assert stored_games()[1]["is_goty"] == 1


def test_sticker_migration_preserves_existing_entries(tmp_path):
    path = tmp_path / "before-stickers.sqlite"
    schema = (Path(__file__).parents[1] / "app" / "schema.sql").read_text(encoding="utf-8")
    old_schema = "\n".join(line for line in schema.splitlines() if "is_favorite" not in line and "is_goty" not in line)
    with sqlite3.connect(path) as db:
        db.executescript(old_schema)
        db.execute("INSERT INTO games (title,platform,status,review) VALUES ('Original','PC','On hold','Keep this')")
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(path)})
    with app.app_context():
        game = get_db().execute("SELECT * FROM games").fetchone()
        assert game["review"] == "Keep this"
        assert game["is_favorite"] == 0
        assert game["is_goty"] == 0
