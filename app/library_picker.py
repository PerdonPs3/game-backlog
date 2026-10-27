"""Explainable suggestions from the current owner's saved library only."""

from fractions import Fraction


MAX_PREFERENCE_GAMES = 60


def preference_games(library):
    """Use one recent platform entry per catalog game, without duplicating signals."""
    seen = set()
    signals = []
    for game in sorted(library, key=lambda row: row['id'], reverse=True):
        catalog_id = game['igdb_id']
        rating = game['rating']
        if catalog_id is None or rating is None or catalog_id in seen:
            continue
        seen.add(catalog_id)
        if rating >= 8 or rating <= 4:
            signals.append(game)
        if len(signals) == MAX_PREFERENCE_GAMES:
            break
    return signals


def recommend(candidates, signals, genre_map):
    """Return tied top matches and their evidence, or an empty fallback pool."""
    ranked = []
    reasons = {}
    for candidate in candidates:
        genres = set(genre_map.get(candidate['igdb_id'], ()))
        if not genres:
            continue
        affinity = {}
        evidence = []
        for source in signals:
            if source['igdb_id'] == candidate['igdb_id']:
                continue
            source_genres = set(genre_map.get(source['igdb_id'], ()))
            if not source_genres:
                continue
            weight = source['rating'] - 7 if source['rating'] >= 8 else source['rating'] - 5
            for genre in source_genres:
                total, count = affinity.get(genre, (Fraction(0), 0))
                affinity[genre] = (total + Fraction(weight, len(source_genres)), count + 1)
            shared = genres & source_genres
            if shared and weight > 0:
                evidence.append((source['rating'], source['id'], source['title'], shared))
        score = sum((total / count for genre, (total, count) in affinity.items() if genre in genres), Fraction(0)) / len(genres)
        positive_genres = {genre for genre, (total, _) in affinity.items() if total > 0}
        evidence = [(rating, entry_id, title, shared & positive_genres)
                    for rating, entry_id, title, shared in evidence if shared & positive_genres]
        if score <= 0 or not evidence:
            continue
        source = max(evidence, key=lambda item: (item[0], item[1]))
        reasons[candidate['id']] = {
            'title': source[2],
            'rating': source[0],
            'genres': sorted(source[3], key=str.casefold)[:2],
        }
        ranked.append((candidate, score))
    if not ranked:
        return [], {}
    best = max(score for _, score in ranked)
    return [game for game, score in ranked if score == best], reasons
