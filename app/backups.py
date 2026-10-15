"""Portable collection backups: local validation only, never credentials or SQL."""

import json
from datetime import datetime, timezone

from app.catalog import collection_cover_url
from app.game_fields import STATUSES, validate_dates
from app.game_lists import MAX_LISTS, clean_list_name


MAX_BACKUP_BYTES = 2 * 1024 * 1024
MAX_BACKUP_GAMES = 5000
BACKUP_FIELDS = (
    "title", "platform", "status", "rating", "review", "igdb_id", "cover_image_id",
    "started_on", "completed_on", "created_at", "is_favorite", "is_goty",
)
FLAG_FIELDS = ("is_favorite", "is_goty")


class BackupError(ValueError):
    pass


def build_backup(rows, lists=None):
    payload = {
        "format": "game-backlog", "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "games": [{field: bool(row[field]) if field in FLAG_FIELDS else row[field]
                   for field in BACKUP_FIELDS} for row in rows],
    }
    if lists is not None:
        payload["lists"] = lists
    return payload


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_backup(raw, include_lists=False):
    if len(raw) > MAX_BACKUP_BYTES:
        raise BackupError("Backup must be no larger than 2 MB.")
    try:
        payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
    except (UnicodeError, ValueError, RecursionError):
        raise BackupError("Please choose a valid Game Backlog JSON backup.") from None
    if not isinstance(payload, dict) or payload.get("format") != "game-backlog" or type(payload.get("version")) is not int or payload["version"] != 1:
        raise BackupError("Unsupported backup format or version.")
    games = payload.get("games")
    if not isinstance(games, list) or len(games) > MAX_BACKUP_GAMES:
        raise BackupError("A backup must contain a list of no more than 5,000 games.")
    result = []
    for number, entry in enumerate(games, start=1):
        try:
            result.append(_validate_entry(entry))
        except (ValueError, TypeError, KeyError):
            raise BackupError(f"Game {number} contains invalid fields. Nothing was imported.") from None
    lists = payload.get("lists", [])
    if not isinstance(lists, list) or len(lists) > MAX_LISTS:
        raise BackupError("A backup can contain no more than 100 lists. Nothing was imported.")
    validated_lists = []
    names = set()
    for item in lists:
        try:
            name = clean_list_name(item["name"])
            members = item["games"]
            if name.casefold() in names or not isinstance(members, list) or len(members) > MAX_BACKUP_GAMES:
                raise ValueError
            if any(type(index) is not int or not 0 <= index < len(result) for index in members):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise BackupError("The backup contains invalid lists. Nothing was imported.") from None
        names.add(name.casefold())
        validated_lists.append({"name": name, "games": sorted(set(members))})
    return (result, validated_lists) if include_lists else result


def _validate_entry(entry):
    if not isinstance(entry, dict):
        raise ValueError
    game = {field: entry.get(field) for field in BACKUP_FIELDS}
    for field in FLAG_FIELDS:
        value = entry.get(field, False)
        if type(value) not in (bool, int) or value not in (0, 1):
            raise ValueError
        game[field] = int(value)
    for field, limit in (("title", 200), ("platform", 80)):
        if not isinstance(game[field], str) or not 0 < len(game[field].strip()) <= limit:
            raise ValueError
        game[field] = game[field].strip()
    if game["status"] not in STATUSES:
        raise ValueError
    rating = game["rating"]
    if rating is not None and (type(rating) is not int or not 1 <= rating <= 10):
        raise ValueError
    if not isinstance(game["review"], str) or len(game["review"]) > 2000:
        raise ValueError
    igdb_id = game["igdb_id"]
    if igdb_id is not None and (type(igdb_id) is not int or not 0 < igdb_id < 2**63):
        raise ValueError
    cover = game["cover_image_id"]
    if cover is not None and (not isinstance(cover, str) or len(cover) > 200 or collection_cover_url(cover) is None):
        raise ValueError
    for field in ("started_on", "completed_on"):
        if game[field] is not None and not isinstance(game[field], str):
            raise ValueError
    if validate_dates(game["started_on"], game["completed_on"]):
        raise ValueError
    created = game["created_at"]
    if not isinstance(created, str) or len(created) > 40:
        raise ValueError
    created_date = datetime.fromisoformat(created)
    if created_date.tzinfo is not None:
        created_date = created_date.astimezone(timezone.utc).replace(tzinfo=None)
    game["created_at"] = created_date.isoformat(sep=" ")
    return game
