# Navigation and canonical destinations

Implemented on `refactor/navigation-flow`; the owner reviewed the local result and authorized develop integration/publication on 2026-10-30, subject to final validation. No schema migration or additional provider is needed. Production remains separate.

## Primary areas

- **Library**: All games, Wishlist, Lists, and Pick a game.
- **Discover**: For you, Popular picks, and Browse & search. The header search opens the same game catalog.
- **Community**: Find players and Connections.
- **Account menu**: My profile, Settings, Data & backups, and Sign out.

Settings opens the profile editor, including its privacy controls, without a
duplicate tab bar. Data & backups is available in the Account menu. Contextual
return links sit below the header so they remain available on small screens.
Uploaded profile backgrounds are resized and optimized locally before upload,
without rejecting the original file for its size, and show an adjustable banner
preview before saving. The original file is unchanged.
The background crop opens in a dialog like the profile-photo editor. Dragging,
arrow keys, zoom, and centering adjust the preview. Use background confirms the
selection; Cancel or Escape preserves the earlier selection. Save changes then
updates the profile. Presets discard pending uploads. The server validates crops.
The player card previews the selected preset or confirmed custom crop immediately;
unconfirmed dialog changes do not alter the card.

The Account menu uses the signed-in owner's private profile photo, falling back
to their initial when no photo is saved. Viewing another player's profile never
changes that menu identity or publishes the owner's photo. Profile pages omit
the redundant header return bar; contextual returns remain on game and editing
screens. This follow-up is local pending owner review and publication approval.

## Flow clarity review — 2026-11-02

Local follow-up on `bugfix/account-avatar-profile-return`, pending review:

- Catalog lookup has one input per lookup screen. Search games and Add game
  use their existing autocomplete; the duplicate global header search is omitted
  on those two screens. Other screens retain the header's Search all games.
- Library and wishlist searches stay scoped to saved entries. Library's input
  explicitly says Search your library; it does not compete with catalog search.
  Clear filters appears only for status, sort, or personal-list selections and
  resets those controls while retaining the title query.
- Wishlist filters saved wishes as the player types, preserving focus and scroll.
  Search is hidden during live filtering and remains available without JavaScript
  or after a failed request. New queries reset pagination; stale responses cannot
  replace newer results. Public wishlists use the same search behavior.
  The private wishlist has one compact heading with its total and visibility;
  Privacy is the only heading action. Wishlist access lives on the profile:
  owners open their managed list and visitors open the shared list when public.
- Discover offers For you, Popular picks, and Search games. The hero no longer
  repeats the catalog-search link, and Search games has its own heading instead
  of inheriting the recommendations headline.
- Library section tabs belong to the four library rooms. Add game uses the main
  Library link and Cancel without a redundant header return bar. Editing and
  other child forms retain contextual returns without a second row of room tabs.
- Connections keeps one contextual Find players action in the list heading,
  alongside the main/section navigation, instead of repeating it in the sidebar
  and empty state. Exact-username requests remain a separate, useful action.
- Private notes has one visible section title and a visually hidden form label.

Regression checks cover search → canonical game page → Add game → return,
and filtered library → Edit → Save/Cancel, together with existing wishlist
transfer, authenticated/anonymous views, old aliases, blocks, and owner isolation.
The browser review used fictional local data and live public catalog metadata:
search → Portal 2 → Edit → Cancel → search retained the original query and
progress anchor. Search was checked at desktop and 390 px in both themes;
Add game has one catalog input and no room-tab row. No shared database changes,
new routes, migrations, or publication are part of this follow-up.

## A shared library shell

All games, Wishlist, Lists, and Pick a game share the same `Your library` heading,
owner-scoped gamepad counter, Add game action, section tabs, and Cards/Shelf control.
The toolbar stays above the section's search or preferences at the same position.
The picker retains its illustrated day/night salon. All games uses the archive,
Wishlist the observatory, and Lists the curator's study, each with day/night art.
Public wishlists retain their separate public layout.

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
rooms travel sideways over 700 ms in adjacent, opaque viewport-sized layers. Direction follows the
tab order, including browser Back/Forward. Content leaves before the camera move
and returns only after the room finishes moving. Outgoing content is hidden
instead of ghosting over a moving scene; arriving content fades in over 120 ms
after the 700 ms room pan. Same-room filtering does not trigger room travel.
Normal links, forms, URL
filters, and browser history remain native. Reduced-motion preferences skip the
animation; browsers without document-transition support navigate normally.
The separate, slower day/night theme dissolve remains unchanged.

Room navigation prepares and decodes the destination's static artwork before
leaving (with a 1.2-second maximum wait). Pointer/focus intent and idle time warm
only the selected theme's artwork, never private page responses; idle warming
respects Save-Data. Rapid clicks while loading choose the latest destination,
and tab/theme clicks during active travel cannot start a competing transition.
Tab clicks during arrival retain only the latest requested destination. The next
trip starts after the current transition finishes and the real page has painted
twice. Room images move exactly one viewport without perspective scaling, so
their edges meet without overlapping or revealing a gap.
During a native view transition, the browser can retarget pointer clicks from a
tab to the document's `<html>` element. While travel is active, primary pointer
clicks on that root are resolved against the stationary toolbar's tab rectangles
and fed into the same last-request queue. Recovery is restricted to the four
same-origin library destinations; it excludes other screen areas, hidden tabs,
keyboard activation, downloads and new-tab targets. It stores no click or filter
history. Browser regression checks replay the eight-click sequence ending in
Lists and a twelve-click reverse sequence ending in Wishlist, then verify the
final active tab and that the transition flag has cleared.
An image failure or timeout falls back to normal navigation without waiting
indefinitely. Arrival does not cancel an already captured outgoing transition
based on the new image element's initial loading flag.
All room snapshots cover the same viewport to avoid a size change at the salon.
The theme toggle is revealed during `pagereveal`, before the navigation snapshot,
so its later initialization cannot shift the header at arrival.

Regression coverage includes owner/other-player/anonymous game views, ID collisions, old owner aliases, manual entries, catalog outages, unsafe return destinations, filtered navigation, login continuation, and wishlist returns. Browser verification uses a local PostgreSQL preview with fictitious accounts, not hosted development or production data.
