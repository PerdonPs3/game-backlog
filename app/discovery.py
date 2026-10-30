"""Owner-only preference ranking over bounded, public catalog candidate pools."""

from fractions import Fraction
from math import ceil

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from app.achievements import normal_owner
from app.catalog import CatalogError, discovery_traits, game_profile, get_catalog
from app.db import get_db
from app.library_picker import preference_games
from app.ownership import owned
from app.public_catalog import catalog_card, public_request_allowed


discovery = Blueprint('discovery', __name__)
GENRES = ('Adventure', 'Arcade', 'Card & Board Game', 'Fighting', 'Hack and slash/Beat \'em up',
          'Indie', 'MOBA', 'Music', 'Pinball', 'Platform', 'Point-and-click', 'Puzzle',
          'Quiz/Trivia', 'Racing', 'Real Time Strategy (RTS)', 'Role-playing (RPG)',
          'Shooter', 'Simulator', 'Sport', 'Strategy', 'Tactical',
          'Turn-based strategy (TBS)', 'Visual Novel')
PLATFORMS = {6: 'PC (Windows)', 48: 'PlayStation 4', 167: 'PlayStation 5',
             49: 'Xbox One', 169: 'Xbox Series X|S', 130: 'Nintendo Switch',
             14: 'Mac', 3: 'Linux', 9: 'PlayStation 3', 12: 'Xbox 360'}
PAGE_SIZE = 12
BROAD_GENRES = {'Adventure', 'Indie', 'Arcade'}
BROAD_THEMES = {'Action', 'Fantasy', 'Science fiction', 'Open world'}


def preference_sources(library, wishes):
    """Ratings take precedence; wishes are weaker than a positive rating."""
    sources = [{**dict(row), 'weight': row['rating'] - (7 if row['rating'] >= 8 else 5),
                'kind': 'rating'} for row in preference_games(library)]
    rated_ids = {row['igdb_id'] for row in library if row['rating'] is not None}
    sources.extend({'igdb_id': row['catalog_id'], 'title': row['title'],
                    'weight': Fraction(1, 2), 'kind': 'wishlist', 'rating': None}
                   for row in wishes[:30] if row['catalog_id'] not in rated_ids)
    return sources


def affinities(sources, genre_map):
    totals = {}
    for source in sources:
        genres = set(genre_map.get(source['igdb_id'], ()))
        for genre in genres:
            total, count = totals.get(genre, (Fraction(0), 0))
            totals[genre] = total + Fraction(source['weight'], len(genres)), count + 1
    return {genre: total / count for genre, (total, count) in totals.items()}


def rank_candidates(candidates, sources, genre_map, trait_map=None):
    """Require specific gameplay evidence and reject known context conflicts."""
    trait_map = trait_map or {}
    affinity = affinities(sources, genre_map)
    theme_affinity = affinities(sources, {key: tuple(set(value['themes']) - BROAD_THEMES)
                                        for key, value in trait_map.items()})
    mechanic_affinity = affinities(sources, {key: value['mechanics'] for key, value in trait_map.items()})
    ranked = []
    for candidate in candidates:
        traits = discovery_traits(candidate)
        genres = set(traits['genres']) - BROAD_GENRES
        themes = set(traits['themes'])
        specific_themes = themes - BROAD_THEMES
        mechanics = set(traits['mechanics'])
        score = sum((affinity.get(genre, 0) for genre in genres), Fraction(0)) / max(1, len(genres))
        score += Fraction(1, 4) * sum((theme_affinity.get(theme, 0) for theme in specific_themes), Fraction(0)) / max(1, len(specific_themes))
        score += Fraction(1, 2) * sum((mechanic_affinity.get(item, 0) for item in mechanics), Fraction(0)) / max(1, len(mechanics))
        evidence = []
        for source in sources:
            if source['igdb_id'] == candidate['id']:
                continue
            source_traits = trait_map.get(source['igdb_id'], {})
            source_genres = set(genre_map.get(source['igdb_id'], ())) - BROAD_GENRES
            source_themes = set(source_traits.get('themes', ()))
            perspectives = set(traits['player_perspectives'])
            source_perspectives = set(source_traits.get('player_perspectives', ()))
            shared_perspectives = perspectives & source_perspectives
            modes = set(traits['game_modes'])
            source_modes = set(source_traits.get('game_modes', ()))
            if ((perspectives and source_perspectives and not shared_perspectives)
                    or (modes and source_modes and not modes & source_modes)
                    or (themes and source_themes and ('Horror' in themes) != ('Horror' in source_themes))):
                continue
            shared = genres & source_genres
            shared = {genre for genre in shared if affinity.get(genre, 0) > 0}
            shared_themes = {theme for theme in specific_themes & source_themes if theme_affinity.get(theme, 0) > 0}
            source_mechanics = set(source_traits.get('mechanics', ()))
            shared_mechanics = {item for item in mechanics & source_mechanics if mechanic_affinity.get(item, 0) > 0}
            mechanic_similarity = Fraction(len(shared_mechanics), max(1, len(mechanics | source_mechanics)))
            similarity = Fraction(len(shared), max(1, len(genres | source_genres)))
            gameplay_match = bool(shared and similarity >= Fraction(1, 2))
            context_match = bool(shared_themes and shared_perspectives and not (genres and source_genres and not shared))
            if source['weight'] > 0 and (gameplay_match or context_match or shared_mechanics):
                labels = sorted(shared_mechanics)[:1] + sorted(shared, key=str.casefold)[:2]
                labels += sorted(shared_perspectives, key=str.casefold)[:1]
                labels += sorted(shared_themes, key=str.casefold)[:1]
                evidence.append((source, sorted(shared, key=str.casefold), similarity,
                                 labels[:3], len(shared_perspectives), mechanic_similarity))
        if score > 0 and evidence:
            source, shared, similarity, labels, _, mechanic_similarity = max(
                evidence, key=lambda item: (item[0]['weight'] * (item[2] + Fraction(item[4], 2) + 2 * item[5]), len(item[1])))
            score *= 1 + similarity + 2 * mechanic_similarity
            ranked.append((score, candidate, {'title': source['title'], 'kind': source['kind'],
                                             'rating': source['rating'], 'genres': shared[:2], 'matches': labels}))
    ranked.sort(key=lambda row: (-row[0], -(row[1].get('total_rating_count') or 0), row[1]['id']))
    return [(candidate, reason) for _, candidate, reason in ranked]


def selected_filters(values):
    genre = values.get('genre', '')
    raw_platform = values.get('platform', '')
    mode = values.get('mode', 'for-you')
    try:
        platform = int(raw_platform) if raw_platform else None
        page = int(values.get('page', '1'))
    except (ValueError, TypeError):
        abort(400)
    if ((genre and genre not in GENRES) or (platform is not None and platform not in PLATFORMS)
            or mode not in ('for-you', 'popular') or not 1 <= page <= 17):
        abort(400)
    return genre, platform, mode, page


@discovery.get('/discover')
def index():
    if current_app.config.get('AUTH_ENABLED') and g.user:
        if g.account_session['recovery']:
            return redirect(url_for('auth.password'))
        if not normal_owner():
            return redirect(url_for('auth.profile'))
    genre, platform, mode, page = selected_filters(request.args)
    personal = normal_owner() or not current_app.config.get('AUTH_ENABLED')
    sources, library, wishes = [], [], []
    if personal:
        db = get_db()
        library = db.execute(f'SELECT id, title, igdb_id, rating FROM games WHERE {owned()} ORDER BY id DESC').fetchall()
        if normal_owner():
            wishes = db.execute('SELECT catalog_id, title FROM wishlist_games WHERE owner_id = ? ORDER BY created_at DESC, catalog_id DESC LIMIT 30', (g.user['id'],)).fetchall()
        if mode == 'for-you':
            sources = preference_sources(library, wishes)
    owned_ids = {row['igdb_id'] for row in library if row['igdb_id'] is not None}
    wished_ids = set()
    if normal_owner():
        wished_ids = {row['catalog_id'] for row in get_db().execute('SELECT catalog_id FROM wishlist_games WHERE owner_id = ?', (g.user['id'],))}
    error, status, genre_map, trait_map, rows, personalized = None, 200, {}, {}, [], False
    if not public_request_allowed():
        error, status = 'The catalog is busy. Please wait a minute and try again.', 429
    else:
        try:
            provider = get_catalog()
            if sources:
                trait_map = provider.get_game_traits([source['igdb_id'] for source in sources])
                genre_map = {key: value['genres'] for key, value in trait_map.items()}
            affinity = affinities(sources, genre_map)
            interests = [key for key, score in sorted(affinity.items(), key=lambda item: (-item[1], item[0]))
                         if score > 0 and key not in BROAD_GENRES][:6]
            candidates = provider.get_discovery_games((genre,) if genre else tuple(interests), platform)
            candidates = [game for game in candidates if game['id'] not in owned_ids
                          and (not genre or genre in game_profile(game)['genres'])
                          and (not platform or any(item.get('id') == platform for item in game.get('platforms', []) if isinstance(item, dict)))]
            ranked = rank_candidates(candidates, sources, genre_map, trait_map) if sources else []
            personalized = bool(ranked)
            rows = ranked if ranked else [(game, None) for game in candidates]
        except CatalogError:
            error, status = 'Recommendations are temporarily unavailable. Please try again shortly.', 503
    pages = max(1, ceil(len(rows) / PAGE_SIZE))
    if not error and page > pages:
        abort(404)
    games = [{**catalog_card(raw), 'genres': game_profile(raw)['genres'][:3],
              'reason': reason, 'wished': raw['id'] in wished_ids}
             for raw, reason in rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]]
    return render_template('discover.html', games=games, genre=genre, platform=platform, mode=mode,
                           genres=GENRES, platforms=PLATFORMS, page=page, pages=pages, total=len(rows),
                           personal=personal, personalized=personalized, error=error,
                           can_save=normal_owner()), status


@discovery.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Referrer-Policy'] = 'same-origin'
    if response.status_code == 429:
        response.headers['Retry-After'] = '60'
    return response
