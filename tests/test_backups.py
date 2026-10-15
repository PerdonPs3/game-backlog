import io
import json

import pytest

from app.backups import MAX_BACKUP_BYTES, BackupError, parse_backup
from tests.conftest import CSRFTokenParser


@pytest.fixture
def backup_entry():
    return {"title": "Portal 2", "platform": "PC", "status": "On hold", "rating": 9,
            "review": "Keep this review", "igdb_id": 123, "cover_image_id": "co_test",
            "started_on": "2026-01-01", "completed_on": None, "created_at": "2026-01-01 12:00:00",
            "is_favorite": False, "is_goty": False}


def encoded(entries, **extra):
    return json.dumps({"format": "game-backlog", "version": 1, "games": entries, **extra}).encode()


def import_file(client, data, confirm=True):
    parser = CSRFTokenParser()
    parser.feed(client.get("/backups/import").get_data(as_text=True))
    fields = {"csrf_token": parser.token, "backup": (io.BytesIO(data), "backup.json")}
    if confirm:
        fields["confirm_import"] = "yes"
    return client.post("/backups/import", data=fields, content_type="multipart/form-data")


def test_export_contains_only_portable_fields_and_no_secrets(client, seed_game):
    seed_game()
    response = client.get("/backups/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json
    assert payload["format"] == "game-backlog"
    assert len(payload["games"]) == 1
    assert "id" not in payload["games"][0]
    assert "SECRET_KEY" not in response.get_data(as_text=True)
    assert "csrf_token" not in response.get_data(as_text=True)


def test_import_round_trip_preserves_personal_fields(client, backup_entry, stored_games):
    assert b"Imported 1 entries" in import_file(client, encoded([backup_entry])).data
    saved = stored_games()[0]
    for field, value in backup_entry.items():
        assert saved[field] == value
    exported = client.get("/backups/export").json
    assert exported["games"] == [backup_entry]


def test_repeated_import_skips_duplicates_without_overwriting(client, backup_entry, stored_games):
    import_file(client, encoded([backup_entry]))
    before = stored_games()
    changed = {**backup_entry, "review": "Overwrite attempt", "rating": 1}
    page = import_file(client, encoded([changed])).data
    assert b"Imported 0 entries. Skipped 1 duplicates" in page
    assert stored_games() == before


def test_duplicate_entries_in_same_file_are_skipped(client, backup_entry, stored_games):
    page = import_file(client, encoded([backup_entry, backup_entry])).data
    assert b"Imported 1 entries. Skipped 1 duplicates" in page
    assert len(stored_games()) == 1


def test_import_allows_same_game_on_different_platforms(client, backup_entry, stored_games):
    import_file(client, encoded([backup_entry, {**backup_entry, "platform": "PlayStation 3"}]))
    assert len(stored_games()) == 2


def test_import_validates_entire_file_before_saving(client, backup_entry, stored_games):
    page = import_file(client, encoded([backup_entry, {**backup_entry, "rating": 11}]))
    assert b"Nothing was imported" in page.data
    assert stored_games() == []


@pytest.mark.parametrize("changes", [
    {"title": ""}, {"title": "x" * 201}, {"platform": None}, {"status": "Unknown"},
    {"rating": True}, {"rating": 8.5}, {"rating": 0}, {"review": "x" * 2001},
    {"review": {}}, {"igdb_id": True}, {"igdb_id": -1}, {"igdb_id": 2**63},
    {"cover_image_id": "https://evil.example"}, {"cover_image_id": "../invalid"},
    {"started_on": "2026-02-30"}, {"started_on": "2026-02-01", "completed_on": "2026-01-01"},
    {"created_at": "not-a-date"},
])
def test_invalid_backup_fields_are_rejected(backup_entry, changes):
    with pytest.raises(BackupError):
        parse_backup(encoded([{**backup_entry, **changes}]))


@pytest.mark.parametrize("data", [b"bad json", b"\xff", b"[]", b'{"version":1,"version":2}', b'{}'])
def test_bad_json_is_rejected(data):
    with pytest.raises(BackupError):
        parse_backup(data)


def test_size_limit_is_enforced():
    with pytest.raises(BackupError, match="2 MB"):
        parse_backup(b" " * (MAX_BACKUP_BYTES + 1))


def test_confirmation_and_csrf_are_required(client, backup_entry, stored_games):
    assert b"Please confirm" in import_file(client, encoded([backup_entry]), confirm=False).data
    assert client.post("/backups/import", data={"backup": (io.BytesIO(encoded([backup_entry])), "b.json")}).status_code == 400
    assert stored_games() == []


def test_imported_text_is_escaped(client, backup_entry):
    import_file(client, encoded([{**backup_entry, "title": "<script>alert(1)</script>"}]))
    assert b"&lt;script&gt;" in client.get("/").data


def test_empty_backup_is_valid(client, stored_games):
    assert b"Imported 0 entries" in import_file(client, encoded([])).data
    assert stored_games() == []


def test_export_is_global_even_when_query_contains_filters(client, seed_game):
    seed_game(title="One", status="Backlog")
    seed_game(title="Two", status="Dropped")
    assert len(client.get("/backups/export?q=One&status=Backlog").json["games"]) == 2


def test_import_manual_entries_and_skip_manual_duplicates(client, backup_entry, stored_games):
    entry = {**backup_entry, "igdb_id": None, "cover_image_id": None}
    import_file(client, encoded([entry, {**entry, "title": "portal 2", "platform": "pc"}]))
    assert len(stored_games()) == 1


def test_missing_file_does_not_save(client, stored_games):
    parser = CSRFTokenParser()
    parser.feed(client.get("/backups/import").get_data(as_text=True))
    response = client.post("/backups/import", data={"csrf_token": parser.token, "confirm_import": "yes"})
    assert b"Please choose a JSON backup file" in response.data
    assert stored_games() == []


def test_too_many_entries_are_rejected(backup_entry):
    with pytest.raises(BackupError):
        parse_backup(encoded([backup_entry] * 5001))
