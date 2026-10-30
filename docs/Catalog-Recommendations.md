# Discover recommendations

Implemented locally on `feature/catalog-recommendations`, based on updated
`develop`. Owner review and separate integration/publication authorization are
pending. No database migration or new provider is required.

## What appears

Discover is available at `/discover` and in the shared navigation. For you ranks
new catalog games using only the current owner's saved ratings and wishlist.
Popular picks bypasses personal taste signals. Anonymous visitors receive a
clearly labeled popular selection and a sign-in invitation. Recovery sessions
and unfinished profiles are redirected through the existing account flow.

Genre and platform filters intersect the results. They are explicit selections
for this visit, preserved in links and history, rather than new stored profile
preferences. Forms and pagination work without JavaScript. With JavaScript,
updates replace the recommendation workspace without a page reload or scroll
reset; aborted/stale responses cannot replace newer selections. Failures retain
the previous results and offer retrying.

Every catalog-linked game in the owner's library is excluded, regardless of
platform or status. Legacy entries without catalog IDs cannot be identified
reliably and do not contribute preference signals. Wishlist games remain visible
with an On your wishlist label. Saving uses the existing CSRF-protected,
provider-revalidated wishlist operation and returns to Discover with its filters.
Merely viewing or filtering recommendations never writes either collection.

## Ranking and explanations

- Use the most recent rated platform entry per catalog game, capped at 60
  positive/negative reference games. Neutral ratings suppress older ratings for
  that same game without becoming positive or negative evidence.
- Ratings of 4 stars or more add genre affinity; ratings of 2 stars or less
  subtract it. The existing ten-step stored rating scale is converted for display.
- Up to 30 recent wishlist games provide a weaker positive signal. A rated game
  takes precedence over its wishlist signal.
- Divide each signal among its known genres, then average contributions per
  genre. Adventure, Indie and Arcade never count as specific gameplay evidence
  or determine the automatic candidate genres. A shared core-genre match must
  cover at least half the union of the two games' core genres. Alternatively,
  a shared specific theme plus a matching perspective may qualify, unless the
  games have disjoint known core genres. Action, Fantasy, Science fiction and
  Open world alone are not specific theme evidence.
- Compare provider-supplied perspectives, themes and play modes in a cached
  batch of at most 90 reference games. Known disjoint perspectives or play modes
  reject an explanation; horror requires horror on the source too. Missing
  metadata remains unknown, never inferred from names or descriptions.
- Explicit gameplay keywords such as Metroidvania, Roguelike, Soulslike and
  Survival horror are normalized through a small vocabulary. Shared mechanics
  supply stronger evidence and ranking bonuses; generic keyword overlap does
  not qualify. These rules apply to all catalog IDs without title exceptions.
- Rank qualified matches by core-genre affinity, a smaller specific-theme
  contribution, and shared-core-genre similarity. Negative scores never become
  personalized recommendations.
- Explanations identify an actual positively contributing rated/wished source
  with specific matching traits. A game never explains itself. Hollow Knight
  cannot explain Outlast through Adventure/Indie; Ori's side-view platforming
  can be explained by Hollow Knight rather than Portal 2's first-person play.
  Popularity breaks score ties. Scores are never
  presented as predicted enjoyment or similarity percentages.
- Without positive matching evidence, explicitly label the results Popular picks.
  Missing genres and provider failures never invent a preference explanation.

Candidate selection uses up to six positively weighted genres, unless the owner
explicitly selects a genre; automatic selection omits the three broad genres.
Each query requests at most 200 released, official
catalog entries, ordered by rating-count popularity, then applies owner exclusion
and ranking locally. This is a bounded selection, not the entire catalog. Pages
contain 12 games. Existing pack, port, variant and community-content exclusions
also run locally. The platform selector currently offers ten common platforms.

## Data and operational boundaries

Only public catalog metadata is cached, for five minutes with at most 32 candidate
pool keys. Per-owner queries, ranking, explanations and wish state are not shared
between accounts. Responses use `private, no-store` and `same-origin` referrers.
The existing warm-process public catalog request budget applies to Discover.

IGDB receives bounded public catalog IDs and genre/platform queries. Account IDs,
ratings, private notes, review text and wishlist contents are never sent as
payloads to a recommendation service. No chatbot, AI provider configuration,
payment service, following feed, hosted migration or production change is part
of this increment. IGDB fields and filtering follow its
[official API documentation](https://api-docs.igdb.com/).

## Courtyard artwork

The owner-approved third Connections mockup is now adapted for Discover. The
clean courtyard backgrounds have aligned day/night lighting, decorative empty
alt text, a container excluded from accessibility, and reduced-motion support.
Opaque surfaces preserve text contrast. Both optimized WebP assets are 1536 ×
1024 pixels. Prompts and built-in ImageGen provenance are saved in
[Discover-Courtyard-Artwork-Prompts.json](Discover-Courtyard-Artwork-Prompts.json).

## Verification

Use fictional accounts and disposable loopback PostgreSQL schemas for automated
tests. Coverage includes account isolation, anonymous browsing, positive/negative
and wishlist evidence, platform-copy deduplication, owned-game exclusion, filters,
pagination, rate limits, provider failures, CSRF, and explicit wishlist saves.
JavaScript tests cover asynchronous replacement, stale responses, edited filters,
failure retention, modified links, and browser history.

The implementation passed 169 relevant Python regression cases on disposable
local PostgreSQL and all 162 JavaScript interaction tests. Browser checks used
the real IGDB catalog with fictional local accounts, including filter updates,
a wishlist save, light/dark desktop layouts and a 390-pixel mobile layout.
No shared database was changed or used for these tests.

The owner-reported Hollow Knight/Outlast mismatch exposed overly broad genre
evidence. Follow-up regressions cover that pair, Ori using Hollow Knight rather
than Portal 2, specific-mechanic ranking, missing metadata, horror/mode/view
conflicts, and self-recommendation from a wishlist entry.
The final follow-up passed 85 discovery/catalog/library-picker regression cases.
The prior boundary run also passed wishlist and public-catalog cases. Browser
verification against live public metadata now shows Silksong, Ori and Metroid
with Metroidvania/platform/side-view evidence from Hollow Knight, without an
Outlast attribution. Matching remains dependent on provider metadata quality.
