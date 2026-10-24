"""Server-side IGDB access. Credentials and tokens never go to the browser."""

import json
import re
from datetime import datetime, timezone
from threading import RLock
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import click
from flask import current_app
from flask.cli import with_appcontext


class CatalogError(Exception):
    """A safe error message that does not expose upstream response bodies."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _request_json(request):
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 429:
            message = "The catalog is busy. Please wait and try again."
        elif error.code in (400, 401, 403):
            message = "Catalog request rejected. Check the IGDB configuration."
        else:
            message = "The catalog is temporarily unavailable."
        raise CatalogError(message, status=error.code) from None
    except (URLError, TimeoutError, OSError):
        raise CatalogError("Could not reach the catalog. Please try again.") from None
    except (ValueError, UnicodeError):
        raise CatalogError("The catalog returned an invalid response.") from None


class IGDBClient:
    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._expires_at = 0
        self._lock = RLock()
        self._last_search_at = 0
        self._search_cache = {}
        self._game_cache = {}
        self._genre_cache = {}

    def _access_token(self):
        if self._token and monotonic() < self._expires_at:
            return self._token

        # Send secrets in the POST body, never in a URL or diagnostic message.
        body = urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }).encode("utf-8")
        payload = _request_json(Request(
            "https://id.twitch.tv/oauth2/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        ))
        if not isinstance(payload, dict):
            raise CatalogError("Twitch returned an invalid authentication response.")
        token = payload.get("access_token")
        lifetime = payload.get("expires_in")
        if not isinstance(token, str) or not token or type(lifetime) is not int or lifetime <= 0:
            raise CatalogError("Twitch returned an invalid authentication response.")

        self._token = token
        self._expires_at = monotonic() + max(0, lifetime - 30)
        return token

    def search_games(self, term, *, include_community=False):
        """Cache short-lived results and serialize this process's API requests."""
        term = term.strip()
        if len(term) > 200:
            raise CatalogError("Search must contain no more than 200 characters.")
        if len(term) < 2:
            return []
        with self._lock:
            cache_key = (term.casefold(), include_community)
            cached = self._search_cache.get(cache_key)
            if cached and monotonic() < cached[0]:
                return cached[1]
            games = self._search_games(term, include_community=include_community)
            if len(self._search_cache) >= 64:
                self._search_cache.clear()
            self._search_cache[cache_key] = (monotonic() + 30, games)
            return games

    def _search_games(self, term, *, include_community=False):
        term = term.strip()
        if len(term) > 200:
            raise CatalogError("Search must contain no more than 200 characters.")
        if len(term) < 2:
            return []

        # Match every word, including aliases, without requiring an exact phrase.
        words = list(dict.fromkeys(re.findall(r"[^\W_]+", term, re.UNICODE)))
        if not words:
            return []
        matches = " & ".join(
            f"(name ~ *{json.dumps(word)}* | alternative_names.name ~ *{json.dumps(word)}*)"
            for word in words
        )
        excluded = ["Bundle", "Pack", "Pack / Addon", "Port", "bundle", "pack", "port"]
        if not include_community:
            excluded.extend(["Mod", "mod", "Fan Game", "fan game"])
        query = (
            f"fields {GAME_FIELDS},total_rating_count,keywords.name; "
            f"where ({matches}) & version_parent = null & game_type.type != "
            f"({','.join(json.dumps(value) for value in excluded)}); "
            "sort total_rating_count desc; limit 500;"
        )
        games = self._query_games(query)
        # Keep distinct remakes/remasters, but never repeat the same catalog ID.
        unique = {}
        for game in games:
            if (not is_game_pack(game) and not is_game_variant(game)
                    and (include_community or not is_community_game(game))):
                unique.setdefault(game["id"], game)
        return sorted(unique.values(), key=lambda game: search_sort_key(game, term))

    def get_game(self, game_id):
        """Resolve a selected ID on the server, not from posted metadata."""
        if type(game_id) is not int or not 0 < game_id < 2**63:
            return None
        with self._lock:
            cached = self._game_cache.get(game_id)
            if cached and monotonic() < cached[0]:
                return cached[1]
            games = self._query_games(
                f"fields {GAME_FIELDS},summary,genres.name,artworks.image_id,screenshots.image_id,videos.name,videos.video_id; where id = {game_id}; limit 1;"
            )
            game = next((g for g in games if g["id"] == game_id), None)
            if game is None or is_game_pack(game) or is_game_variant(game):
                return None
            if len(self._game_cache) >= 128:
                self._game_cache.clear()
            self._game_cache[game_id] = (monotonic() + 300, game)
            return game

    def get_game_genres(self, game_ids):
        """Fetch only pending-game genres in batches, not one request per entry."""
        ids = sorted({value for value in game_ids if type(value) is int and 0 < value < 2**63})
        with self._lock:
            now = monotonic()
            missing = [value for value in ids
                       if value not in self._genre_cache or now >= self._genre_cache[value][0]]
            for start in range(0, len(missing), 200):
                batch = missing[start:start + 200]
                query_ids = ",".join(str(value) for value in batch)
                games = self._query_games(
                    f"fields id,name,genres.name; where id = ({query_ids}); limit 200;"
                )
                by_id = {game["id"]: tuple(game_profile(game)["genres"]) for game in games
                         if game["id"] in batch}
                # Missing games have no known genre; never guess from their titles.
                for value in batch:
                    self._genre_cache[value] = (monotonic() + 300, by_id.get(value, ()))
            result = {value: self._genre_cache[value][1] for value in ids}
            if len(self._genre_cache) > 5000:
                self._genre_cache.clear()
            return result

    def _query_games(self, query):
        query = query.encode("utf-8")

        for attempt in range(2):
            token = self._access_token()
            request = Request(
                "https://api.igdb.com/v4/games",
                data=query,
                headers={
                    "Client-ID": self._client_id,
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "text/plain",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                delay = 0.26 - (monotonic() - self._last_search_at)
                if delay > 0:
                    sleep(delay)
                self._last_search_at = monotonic()
                games = _request_json(request)
            except CatalogError as error:
                if error.status == 401 and attempt == 0:
                    self._token = None
                    self._expires_at = 0
                    continue
                raise

            if not isinstance(games, list) or any(
                not isinstance(game, dict)
                or type(game.get("id")) is not int
                or game["id"] <= 0
                or not isinstance(game.get("name"), str)
                or not game["name"].strip()
                for game in games
            ):
                raise CatalogError("The catalog returned invalid game data.")
            return games


GAME_FIELDS = (
    "id,name,first_release_date,cover.image_id,platforms.id,platforms.name,"
    "game_type.type,version_parent,ports.platforms.id,ports.platforms.name"
)


def search_sort_key(game, term):
    """Prefer exact titles and official entries, then rating-count popularity."""
    title = " ".join(game["name"].casefold().split())
    search = " ".join(term.casefold().split())
    relevance = 0 if title == search else 1 if title.startswith(search) else 2
    count = game.get("total_rating_count")
    popularity = count if type(count) is int and count > 0 else 0
    return (0 if relevance == 0 else 1, is_community_game(game), -popularity,
            relevance, *release_date_sort_key(game))


def is_community_game(game):
    """Use provider classification, never infer licensing from a title."""
    kind = game.get("game_type")
    if isinstance(kind, dict) and str(kind.get("type", "")).casefold() in ("mod", "fan game", "fangame"):
        return True
    keywords = game.get("keywords", [])
    if not isinstance(keywords, list):
        return False
    return any(isinstance(keyword, dict) and any(
        marker in str(keyword.get("name", "")).casefold()
        for marker in ("fangame", "fan game", "rom hack", "romhack")
    ) for keyword in keywords)


def release_date_sort_key(game):
    """Newest first, unknown/invalid dates last, stable ties by title and ID."""
    timestamp = game.get("first_release_date")
    if type(timestamp) is int:
        try:
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            timestamp = None
    else:
        timestamp = None
    return (timestamp is None, -timestamp if timestamp is not None else 0,
            game["name"].casefold(), game["id"])


def is_game_variant(game):
    game_type = game.get("game_type")
    return bool(game.get("version_parent")) or (
        isinstance(game_type, dict)
        and str(game_type.get("type", "")).casefold() == "port"
    )


def is_game_pack(game):
    game_type = game.get("game_type")
    return isinstance(game_type, dict) and str(game_type.get("type", "")).casefold() in (
        "bundle", "pack", "pack / addon",
    )


def cover_image_id(game):
    cover = game.get("cover")
    image_id = cover.get("image_id") if isinstance(cover, dict) else None
    if isinstance(image_id, str) and re.fullmatch(r"[A-Za-z0-9_]+", image_id):
        return image_id
    return None


def collection_cover_url(image_id):
    """Revalidate stored IDs and keep collection images on the fixed IGDB host."""
    if cover_image_id({"cover": {"image_id": image_id}}) is not None:
        return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
    return None


def game_suggestion(game):
    """Expose only public display metadata, with a fixed image host."""
    year = None
    timestamp = game.get("first_release_date")
    if type(timestamp) is int:
        try:
            year = datetime.fromtimestamp(timestamp, tz=timezone.utc).year
        except (ValueError, OverflowError, OSError):
            pass

    cover_url = None
    image_id = cover_image_id(game)
    if image_id is not None:
        cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_small/{image_id}.jpg"

    platforms = game.get("platforms", [])
    if not isinstance(platforms, list):
        platforms = []
    platforms = list(platforms)
    ports = game.get("ports", [])
    if isinstance(ports, list):
        for port in ports:
            if isinstance(port, dict) and isinstance(port.get("platforms"), list):
                platforms.extend(port["platforms"])
    names = sorted({p["name"].strip() for p in platforms
                    if isinstance(p, dict) and isinstance(p.get("name"), str)
                    and 0 < len(p["name"].strip()) <= 80}, key=str.casefold)
    return {
        "id": game["id"],
        "name": game["name"],
        "year": year,
        "cover_url": cover_url,
        "platforms": names,
    }


def game_media(game):
    """Expose bounded, validated media on fixed provider hosts only."""
    items, seen = [], set()
    videos = game.get('videos')
    if isinstance(videos, list):
        for video in videos:
            if not isinstance(video, dict):
                continue
            video_id = video.get('video_id')
            if not isinstance(video_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) or video_id in seen:
                continue
            seen.add(video_id)
            title = video.get('name')
            items.append({'kind': 'video', 'id': video_id,
                          'title': title[:160] if isinstance(title, str) and title.strip() else 'Trailer',
                          'preview': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
                          'url': f'https://www.youtube.com/watch?v={video_id}'})
            if len(items) == 4:
                break
    screenshots = game.get('screenshots')
    if isinstance(screenshots, list):
        for image in screenshots:
            image_id = cover_image_id({'cover': image})
            if not image_id or image_id in seen:
                continue
            seen.add(image_id)
            items.append({'kind': 'image', 'id': image_id, 'title': f'Screenshot {sum(item["kind"] == "image" for item in items) + 1}',
                          'preview': f'https://images.igdb.com/igdb/image/upload/t_screenshot_med/{image_id}.jpg',
                          'url': f'https://images.igdb.com/igdb/image/upload/t_screenshot_huge/{image_id}.jpg'})
            if sum(item['kind'] == 'image' for item in items) == 8:
                break
    return items


def game_profile(game):
    """Public catalog details, with safe defaults for optional upstream fields."""
    release = None
    timestamp = game.get("first_release_date")
    if type(timestamp) is int:
        try:
            release = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            pass
    genres = game.get("genres", [])
    if not isinstance(genres, list):
        genres = []
    names = sorted({genre["name"].strip()[:100] for genre in genres
                    if isinstance(genre, dict) and isinstance(genre.get("name"), str)
                    and genre["name"].strip()}, key=str.casefold)
    summary = game.get("summary")
    backdrop = None
    for field in ('artworks', 'screenshots'):
        images = game.get(field)
        if isinstance(images, list):
            for image in images:
                image_id = cover_image_id({'cover': image})
                if image_id:
                    backdrop = f'https://images.igdb.com/igdb/image/upload/t_screenshot_huge/{image_id}.jpg'
                    break
        if backdrop:
            break
    if not backdrop:
        backdrop = collection_cover_url(cover_image_id(game))
    return {"release": release, "genres": names, "backdrop_url": backdrop, "media": game_media(game),
            "summary": summary[:12000] if isinstance(summary, str) else None}


def get_catalog():
    if "igdb_client" not in current_app.extensions:
        client_id = current_app.config.get("IGDB_CLIENT_ID", "")
        client_secret = current_app.config.get("IGDB_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise CatalogError("Add IGDB_CLIENT_ID and IGDB_CLIENT_SECRET to instance/config.py.")
        current_app.extensions["igdb_client"] = IGDBClient(client_id, client_secret)
    return current_app.extensions["igdb_client"]


@click.command("check-igdb")
@with_appcontext
def check_igdb_command():
    """Check configured IGDB access without writing to the collection."""
    try:
        games = get_catalog().search_games("Resident Evil")
    except CatalogError as error:
        raise click.ClickException(str(error)) from None

    click.echo("IGDB connection successful.")
    click.echo(f"Found {len(games)} matching games:")
    for game in games:
        click.echo(f"- {game['name']} (IGDB ID: {game['id']})")
