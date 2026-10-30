# Navigation and canonical destinations

Implemented locally on `refactor/navigation-flow`; integration and publication require owner authorization. No schema migration or additional provider is needed.

## Primary areas

- **Library**: All games, Wishlist, Lists, and Pick a game.
- **Discover**: For you, Popular picks, and Browse & search. The header search opens the same game catalog.
- **Community**: Find players and Connections.
- **Account menu**: My profile, Settings, Data & backups, and Sign out.

Settings contains Profile, Privacy, and Data & backups. Contextual return links sit below the header so they remain available on small screens.

## A shared library shell

All games, Wishlist, Lists, and Pick a game share the same `Your library` heading,
owner-scoped gamepad counter, Add game action, section tabs, and Cards/Shelf control.
The toolbar stays above the section's search or preferences at the same position.
The picker retains its illustrated day/night salon; the other private library tabs
use the archive background. Public wishlists retain their separate public layout.

Validated collection search, status, sort, and personal-list filters travel between
tabs in local `from` context. Live filtering updates sibling links as well. Return
context remains in the current journey's URL; shared browser storage and account
history are not used for these filters. A removed
or foreign list is discarded from the return context. Cards/Shelf on a sibling tab
opens All games in that view with the retained collection filters.

## Canonical routes

| Purpose | Address |
| --- | --- |
| Personal collection | `/library` |
| Wishlist | `/library/wishlist` |
| Lists | `/library/lists` |
| Owned-game picker | `/library/pick` |
| Add an entry | `/library/add?game=<catalog_id>` |
| Edit or remove an entry | `/library/entries/<entry_id>/edit` or `/delete` |
| Manual entry without catalog metadata | `/library/entries/<entry_id>` |
| Recommendations | `/discover` |
| Catalog search | `/discover/browse?q=<title>` |
| Public game and the viewer's private progress | `/games/<catalog_id>/<title-slug>` |
| Player search | `/community/players` |
| Personal connections | `/community/connections` |
| Player profile | `/players/<username>` |
| Shared wishlist | `/players/<username>/wishlist` |
| Shared follows | `/players/<username>/followers` or `/following` |
| Profile and privacy settings | `/settings/profile` |
| Showcase settings | `/settings/profile/showcase` |
| Backups | `/settings/data` |

Catalog IDs and private entry IDs are different identifiers. `/games/<number>` remains an owner-protected **legacy entry** address; it must never be interpreted as a public catalog ID.

## One game destination

Linked covers, titles, recommendations, reviews, and showcase cards open the modern game page. It presents catalog information, media, and public reviews. A signed-in owner also sees **Your progress**, with a separate entry for each platform, private notes, rating, dates, stickers, and edit/remove actions. Other players and anonymous visitors never receive those entries. Responses use `private, no-store`.

The old collection dialog and its JavaScript are retired. Legacy private JSON fragments remain compatible. Manually created entries without a catalog ID retain an owner-only fallback page. When the catalog is unavailable, saved entry information still lets the owner read and edit their progress.

## Context and compatibility

Game links carry a bounded, validated local `from` destination. Edit/Cancel/Save preserve it, including filters and the private progress anchor. Login can resume a pending authorized GET destination for up to 30 minutes. It cannot replay a mutation. Shared game links omit navigation context.

`app/navigation.py` accepts known GET destinations only, rejects external URLs, actions, control characters and oversized inputs, and bounds nested origins and query fields. Authentication, CSRF, recovery restrictions, profile visibility, bilateral blocking, and SQL ownership remain enforced by the destination.

`app/account_urls.py` preserves old bookmarks and form endpoints. Successful legacy GET pages redirect to canonical addresses; owner-name aliases still validate ownership before redirecting. Public profile aliases retain privacy checks. Old POST endpoints execute their original guarded action once, without redirecting before the write.

## Validation

### Private library rooms and transitions

The owner's Wishlist uses the collector's observatory and Lists uses the curator's
study. Both have separate day/night WebP artwork under `app/static/images/backgrounds/`
(`wishlist-observatory-*` and `lists-study-*`). All games keeps the archive and
Pick a game keeps the salon. Public wishlists keep their existing public layout.

Private library documents opt into native cross-document view transitions. The
site header, library title, and toolbar keep their positions while the illustrated
rooms travel sideways over 700 ms with subtle perspective. Direction follows the
tab order, including browser Back/Forward. Content leaves before the camera move
and returns near arrival. Same-room filtering does not trigger room travel.
Normal links, forms, URL
filters, and browser history remain native. Reduced-motion preferences skip the
animation; browsers without document-transition support navigate normally.
The separate, slower day/night theme dissolve remains unchanged.

Regression coverage includes owner/other-player/anonymous game views, ID collisions, old owner aliases, manual entries, catalog outages, unsafe return destinations, filtered navigation, login continuation, and wishlist returns. Browser verification uses a local PostgreSQL preview with fictitious accounts, not hosted development or production data.
