# Public catalog and shareable game pages

Visitors can browse `/explore` without an account. Search uses a normal GET form
with a 2–200 character query and 30 results per page. `/explore/games/<catalog_id>`
is a standalone page that opens directly, survives refresh, and can be shared.
The ID belongs to IGDB, never to a private collection entry.

Pages show only explicitly projected catalog metadata: title, validated artwork,
release date, genres, synopsis, and available platforms. Optional data has clear
fallbacks. Metadata is escaped by Jinja and artwork uses the existing fixed IGDB
image host. Provider failures return generic 503 messages; unknown games return
404. Credentials, tokens, upstream response bodies, and private library data are
never included in the public projection.

## Entry points and private notes

- The welcome page and library navigation link to Explore.
- Catalog-linked library covers and titles open the public game page. **My entry**
  opens the existing private detail dialog for notes, progress, and personal ratings.
- Legacy entries without a catalog ID keep their private detail behavior.
- Shared profile showcases link to the public catalog when an IGDB ID is available;
  they never link to private game entry IDs.
- Add game retains its convenient picker and also links to the full catalog. Both
  experiences use the same IGDB client, validated selection, and platform rules.
- Discover can reuse these destinations when that milestone is implemented.

**Share** opens native sharing when available, otherwise copies the public URL.
Only the current origin and path are shared, excluding query strings and fragments.
Cancelling native sharing does not copy anything or show an error. If native
sharing fails, clipboard sharing remains available; without either API the page
shows the public link for manual copying. Repeated clicks cannot open concurrent
share requests. Search and game pages work without JavaScript.

## From discovery to collection

**Add to my library** starts `/explore/games/<catalog_id>/add`. This GET request
never inserts a library entry. Anonymous visitors sign in; unfinished accounts
complete their profile first. The selected positive, bounded integer ID is held
in the signed session for up to 30 minutes in the same browser, including through
registration confirmation, login session rotation, and password recovery. No
arbitrary return URL is accepted. Expired, malformed, or future-dated selections
are discarded. Logging out explicitly clears the selection.

After authentication and setup, `/games/new?igdb_id=<catalog_id>` resolves the
game again on the server and preselects its title and supported platforms. The
user must choose a platform and submit the existing CSRF-protected form. POST
revalidates the upstream identity and platform, preserves account ownership, and
retains the existing duplicate game/platform check. Browsing, sign-in, profile
creation, and GET requests never silently add a game.

New profile setup opens the completed profile overview first. If a catalog game
was selected before registration, an explicit Continue to your selected game link
resumes its add flow; the selection remains subject to its original expiry.
Existing members signing in from a game still return directly to the add form.

The existing `/catalog/search` and `/catalog/games/<id>` JSON picker endpoints
remain protected on hosted installations. The public HTML pages are separate
from the private collection routes; both use the same catalog service.

## Provider budget and deployment

The existing IGDB client caches searches for 30 seconds (up to 64 terms), details
for 300 seconds (up to 128 IDs), serializes provider calls, and spaces upstream
requests by at least 0.26 seconds within a process. Public search and detail pages
add a shared rolling budget of 60 requests per minute per warm application process,
configurable with `PUBLIC_CATALOG_REQUEST_LIMIT`. Empty or invalid searches do
not call IGDB. Exhausting the budget returns 429 and `Retry-After: 60`.

This process-local budget is not a distributed quota across Vercel instances.
Use platform-level controls when a deployment needs a global traffic policy.
Responses use private, no-store caching because navigation can reflect the viewer's
account. Provider metadata caches contain no collection data.

No new database migration is required for this increment. It uses the account
schema already introduced by migrations 001–006. Integrate and publish to develop
only after explicit authorization; production publication remains a separate step.
Vercel Preview protection is a separate hosting gate; anonymous application access
does not change that protection.

## Header search and personal game actions

Internal pages include a compact catalog search in the sticky site header. It
submits to Explore with the same query bounds and default official-game filter;
it does not replace the library's collection-only filter. The homepage retains
its existing hero search. On small screens, header search occupies a second row.

Game details provide a personal sidebar for completed, non-recovery sessions.
Players can choose a platform, status, and optional rating and explicitly submit
to the existing CSRF-protected Add game endpoint. The endpoint revalidates catalog
identity, platform, rating, and owner-scoped duplicates, then redirects back to
the game page. More options opens the full form for reviews, dates, and stickers.
The sidebar lists only the current owner's saved entries and offers their edit
links. Anonymous, incomplete-profile, and recovery sessions use the existing
sign-in/setup continuation instead. Responses remain private and non-cacheable;
shared URLs do not carry private entry IDs or ratings.

All rating labels, tooltips, personal scores, and averages use a five-star scale,
including half-star steps. Internally, ratings remain integer half-star units
(1–10), preserving existing entries and backup compatibility without migration.
Native radio controls work with keyboard input and without JavaScript; Clear
submits the existing empty-rating value. Saved ratings and database schema are
unchanged. The same picker is used in the full Add/Edit forms.

## Search suggestions

Search matches title words and alternative names without requiring a contiguous
phrase. It requests up to 500 candidates ordered by IGDB rating count, then ranks
exact titles, non-community entries, popularity, title prefixes, and release dates.
This bounded candidate set avoids the previous 30-result cutoff that could hide
major series entries. It is not an exhaustive download of the provider catalog;
refine broad queries when the candidate limit is reached.

Explore provides Previous/Next links that retain the query and content filter.
The default `content=official` excludes Mod/Fan Game types and keywords containing
fangame, fan game, rom hack, or romhack. `content=all` includes community entries,
labelled in the result grid. This uses IGDB metadata, not a licensing verification;
untagged fan games can remain. Independent games are not excluded for being indie.
Existing pack, port, and version exclusions still apply to both modes.
The Add game picker offers the same filter; homepage suggestions default to official.
Filters apply before pagination and suggestion truncation, and cache keys include
the filter so results cannot leak between the two modes. Changing a filter cancels
pending suggestions and queries the new scope. Search filters never alter an entry
already stored in a player's library or block direct catalog links.

Explore reuses the Add game picker: after 2 characters and a 450 ms pause,
`GET /explore/suggestions?q=...` returns up to 10 public catalog matches with
covers and release years. Clicking or using arrow keys and Enter opens the
selected public game page. Escape, blur, and outside clicks close suggestions;
outdated requests are cancelled and ignored. The normal Search form still works
without JavaScript. Suggestions share the public request budget and IGDB cache;
provider errors return generic messages and never expose collection data.
