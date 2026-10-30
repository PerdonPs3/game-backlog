# Player following

Published to `develop` on 2026-10-30 with explicit owner authorization, preserving
the task branch and a `--no-ff` merge. Migration `017_player_following.sql` was
validated on disposable local PostgreSQL before the owner separately authorized
its application to hosted development. Production remains unchanged.

## Relationship rules

- Completed, normal account sessions can follow another current username.
  Public profiles accept immediately; private profiles receive a pending request.
- The Connections page supports exact-username requests, including private
  players, without adding private players to search. The response does not
  disclose whether an unknown, blocked, or private target exists.
- Private profiles retain their existing 404 behavior for every visitor,
  including accepted followers. Following never unlocks private libraries,
  notes, hidden profile sections, photos, or wishlists.
- Only the recipient can approve or decline an incoming request. Senders can
  cancel requests, and either account can end its corresponding relationship.
  Removing a follower does not prevent them from following again; use Block.
- Existing accepted connections survive a profile becoming private. Profile
  content and shared connection lists disappear immediately. Pending requests
  remain pending if the target later becomes public, until approved or cancelled.
- Relationships use immutable account IDs, so renaming keeps relationships
  intact. New follow requests accept current usernames only, not old aliases.

## Privacy and blocking

Followers/following sharing defaults to off for existing and new accounts. Edit
profile offers one explicit opt-in for both lists and their counts. Public lists
include only completed public profiles; their counts use that same projection.
Owners see all their connections and requests, with private players represented
by their current handle and a neutral label, never their display name or photo.
Hiding your own lists does not remove your public handle from someone else's list.

Connection cards reuse the existing revocable public-photo endpoint and show a
neutral silhouette when a photo is absent or unshared. Private and blocked
identities never expose photos, biography, country, or avatar colors. Public
biographies are included only with their sharing flag, bounded to 140 characters.
The connection workspace includes count navigation, responsive player cards,
keyboard-accessible action menus, and a Follow back shortcut using the existing
CSRF-protected follow operation. Private follow-backs remain approval requests.

Blocking removes accepted and pending connections in both directions atomically.
While signed in, both sides are excluded from each other's player search,
connection lists, public profiles (including old aliases), photos, custom
backgrounds, wishlists, and catalog review projections. Unblocking removes only
your own block and never restores relationships. Blocks do not make public
content secret: anonymous visitors can still view public content.

All changes require CSRF-protected POSTs and derive the acting account from the
session. Recovery and unfinished sessions cannot manage connections. Sorted
profile row locks serialize following, approval, and blocking with privacy edits.
A persistent per-account hourly budget limits new follow attempts, including
unknown and blocked targets; cancelling, removing, and blocking remain available.
Lists are paginated at 20 rows, responses are private/no-store, and relationship
tables have RLS enabled without public client grants.

There is no activity feed, email/push notification, or profile reporting/moderation
workflow in this increment. Existing public review reports remain supported;
broader profile reporting is a separate moderation delivery.

## Local verification

Validated on Python 3.12.2 and disposable local PostgreSQL: 618 Python tests and
157 dependency-free JavaScript interaction tests passed. The following suite
covers request ownership, privacy revocation, bilateral blocks, username changes,
pagination, CSRF/session boundaries, rate limits, and concurrent follow/block
writes. Desktop and 390 px mobile layouts were reviewed in light and dark themes.
Shared development and production databases were not migrated or used for tests.

The connection-card redesign passed 32 targeted following and community-profile
regression cases, including photo opt-out/revocation, private and blocked avatar
exclusion, escaped public bios, and follow-back behavior. Published photos were
also verified in the browser with responsive light/dark layouts.

## Portrait gallery background

The owner selected the portrait-gallery concept for Connections. The gallery
belongs to the same illustrated castle as the library and Add game map room:
framed adventurer portraits, stone arches, navy banners, and a tall central
window. Dark mode uses moonlight and warm lanterns; light mode uses the aligned
daylight version. The existing theme switch handles the change, with reduced
motion support. Neutral translucent surfaces preserve contrast independently of
the scene, and decorative imagery is excluded from the accessibility tree.

Both optimized WebP assets are 1536 × 1024 pixels, stored under
`app/static/images/backgrounds/connections-gallery-{day,night}.webp`. The built-in
ImageGen prompts and provenance are preserved in
[Connections-Gallery-Artwork-Prompts.json](Connections-Gallery-Artwork-Prompts.json).
The separate moonlit courtyard concept is being adapted locally for Discover on
`feature/catalog-recommendations`; see [Catalog recommendations](Catalog-Recommendations.md).
