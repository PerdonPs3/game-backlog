# Public catalog and shareable game pages

Visitors can browse `/explore` without an account. Search uses a normal GET form
with a 2–200 character query and at most 30 results. `/explore/games/<catalog_id>`
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

**Copy link** copies only the current origin and path, excluding query strings and
fragments. If the clipboard API is unavailable or denied, visitors can copy the
browser address. Search and game pages work without JavaScript.

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
