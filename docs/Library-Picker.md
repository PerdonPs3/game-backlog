# Library suggestions

What should I play? supports two explicit modes and multiple library states.
The default pool is Backlog. Playing, On hold, Completed, and Dropped must be
selected explicitly. Platform and genre filters intersect that pool; selecting
no states produces a helpful message without silently reverting to Backlog.
Repeat links preserve the mode, states, platform, and genre. Reset returns to
Backlog with no platform or genre preference.

## For you

Recommendations use only the current owner's library and existing ratings.
The most recently added rated platform entry represents each catalog game,
so owning several copies does not multiply preference signals. At most 60
distinct positive or negative reference games are used.

- Ratings of 4 stars or more contribute positive genre evidence.
- Ratings of 2 stars or less contribute negative genre evidence.
- Ratings between those thresholds are neutral.
- A candidate never supplies evidence for recommending itself.

Evidence is divided across each reference game's known genres, averaged per
genre, and averaged across the candidate's genres. The highest positive matches
form the recommendation pool; ties are resolved randomly. The explanation names
an actual positively rated reference game, its rating, and shared genres with
positive net evidence. This is a genre match, not an AI-generated review or a
prediction of how much the user will enjoy a game.

No positive matches, missing genre metadata, and catalog outages produce an
explicitly labelled random fallback. An unavailable selected genre never causes
the filter to be silently ignored. Manual entries without catalog genres remain
eligible for random selection when Any genre is selected.

## Random and privacy

Every matching platform entry has an equal chance in Random mode. The existing
roulette reveals the server-selected winner; it never changes the result.
Personalized results appear directly with their explanation. Both modes leave
library states, ratings, notes, and public reviews unchanged.

All source queries use the authenticated owner's predicate. Responses are
non-cacheable. Genre metadata is fetched through the existing bounded, cached
IGDB batches; no ratings or review text are sent to a new service. No AI provider,
paid service, database migration, or hosted data change is required.

Implementation is local on `feature/personalized-library-picker` for owner review.
Integration and publication require separate authorization.
