# Private accounts and isolated environments

Hosted PostgreSQL installations require Supabase Auth. SQLite remains an offline,
single-user mode. Account pages are under `/account`; `/` remains public.

## Profile and account addresses

`/profile/<username>` is the canonical profile address. A verified owner sees
private progress and editing controls at that address; visitors and other signed-in
accounts see only the owner's public projection. Private profiles return 404 to
visitors while remaining accessible to their owner. Historical usernames redirect
to the current name only when that viewer may access the destination. Every
private query uses the session owner ID, never a URL-supplied identity.

The library remains `/account/<username>/library`. Editing and showcase routes
remain under `/account/<username>/profile/edit` and `/showcase`. **Edit profile**
now includes username, identity, photo, and all sharing controls in one atomic
save. Legacy sharing GET routes redirect to its privacy section; existing POST
forms retain CSRF checks and ownership validation. Legacy account profile routes
redirect to the canonical profile, and old `/players/<username>` links remain
compatible. Responses vary by Cookie and are private and non-cacheable.

Normal logins use an opaque, persistent HttpOnly browser cookie and a rolling
30-day server session. Provider access and refresh tokens remain server-side.
Expired provider tokens still rotate under a row lock; logout revokes the server
session, including copies of that browser cookie. Recovery sessions are
non-persistent, last at most 30 minutes, and cannot access private collections.

### Profile defaults and deployment

Apply `011_profile_sharing_defaults.sql` before deploying this increment. It
changes defaults for **new** bio and showcase sharing flags without updating
existing rows. Setup selects Public and the available profile details, including
photo sharing, with visible private/unsharing options before saving. Unfinished
accounts remain unpublished until a valid username and display name exist.
Existing privacy choices are preserved, including when an older profile form is
submitted without the new privacy controls. Email, library entries, ratings, and
reviews are never made public by these defaults.

Catalog pages use `Referrer-Policy: same-origin`: HTTPS form POSTs retain the
same-origin Referer required by Flask-WTF, while external sites receive none.
Quick add refreshes its browser-bound CSRF token before submitting; session or
network failures display an actionable message. A stale native quick-add form
returns to the game without writing anything. Cross-origin form submissions
remain rejected, even with a syntactically valid token.

## Optional public player identity

### Server-assigned Creator badge

Migration `009_profile_admin_badge.sql` adds an `admin_badge` flag, disabled for
every existing and new account. The displayed label is **Creator**; the initial
internal field and command names remain compatible. This is a cosmetic identity badge, never an
authorization role. It does not change access to accounts, collections, or pages.
There is no browser form or HTTP endpoint that assigns it. Apply the migration to
the intended environment before serving the updated application.

After verifying the target account and environment, use the server-only command:

```powershell
python -m flask --app wsgi set-admin-badge --username m4ckay
python -m flask --app wsgi set-admin-badge --username m4ckay --apply
```

The first command inspects the current username without changes. The second
assigns the badge to that account's immutable ID. Renaming the account preserves
the badge; another account never inherits it by username matching. Use the current
username with `--remove --apply` to revoke it. Editor, private profile, and public
profile share the same badge rendering. A private public-profile URL still returns
404. Grants in development do not propagate to production.

### Optional country flag

Migration `007_profile_country.sql` adds a nullable ISO 3166-1 country code.
Migration `008_country_profile_visibility.sql` removes the initial separate
country-sharing flag so country visibility follows profile visibility. Apply both
explicitly to the isolated development database before publishing this increment;
production migration requires separate authorization. Existing countries and
profile visibility choices are preserved.

Create/Edit profile includes an optional Country selector. Not specified removes
the saved country and flag. The private profile and editor show a small flag
beside the display name. Public profiles show the selected country automatically;
private profiles remain hidden from visitors. There is no separate country-sharing
checkbox. The country is selected manually, never inferred from location, IP
address, or Steam.

The allowlist, English names, and local SVG icons are bundled from flag-icons
7.6.0 (MIT), with attribution and license in `app/static/images/flags/`.
There are no browser requests to an external flag service. Unknown codes are
rejected on the server and by a database constraint. SQLite offline mode does
not expose account country settings.

Migration `005_public_profiles.sql` adds a unique, nullable username and three
sharing flags, initially disabled in that historical migration. Migration 011 changes only new bio/showcase defaults. It does not publish
existing accounts. The application now selects Public when creating a new profile;
the user can choose Private before saving. Setup reserves a required username and
saves the profile and its visibility atomically. Username history also requires
`006_username_history.sql`, described below.
Apply it explicitly to the isolated development database before deploying this
version, following the environment checks below. Production needs separate
authorization.

After completing profile setup, open **My profile → Edit profile → Privacy & sharing**. Usernames
accept 3–24 ASCII letters, numbers, or underscores, start with a letter, and exclude
reserved service names. Both the browser and server accept capitals; the saved
identity and link are normalized to lowercase. Migration `006_username_history.sql`
adds a shared reservation registry and the last username assignment time. Apply
it explicitly to development before publishing this version. Existing names are
backfilled without changing publication settings. Existing accounts may rename
immediately once because the previous assignment time was not recorded.

New assignments and renames start a 30-day cooldown, measured in exact seconds by
the database clock after locking the account row. Saving the same normalized
username, editing other profile fields, or changing visibility never restarts it.
The editor displays the next available date and time in UTC; changing visibility
and display names remains possible during the cooldown. Rename attempts during
the cooldown or claims of unavailable names roll back every setting in that save.

The registry reserves current and past usernames in one namespace. Other accounts
cannot claim old links, including through profile setup. The owner may reuse an
old name after the cooldown. A composite foreign key binds the current username
to its registry owner, and a database unique constraint resolves concurrent
claims. Names remain reserved while the profile is private.

Old `/players/<username>` URLs issue a temporary, non-cacheable redirect directly
to the latest public username, without chains. Current and old URLs all return
404 while the profile is private. Renaming never publishes a private profile
unless the owner also chooses Public in that save. Historical names and timestamps
are not included in public profile markup. Registry RLS is enabled without
granting public Data API access.

Public is the default for new profiles. Existing saved privacy choices are preserved.
Older named profiles without usernames stay unpublished until they save a valid identity; saved privacy choices are retained. `/players/<username>` works without
signing in only when the profile is Public. The owner chooses separately whether
to share the bio, ordered showcase, statistics, and recent activity. Display name, username, and silhouette
color form the minimum public identity. Subsequent changes to shared fields also
update the public page. Unpublishing returns the same 404 as an unknown username,
for legacy public-only URLs; the canonical profile remains accessible to its verified owner. Responses use `no-store` and `noindex, nofollow`; these do not
make an enabled public URL secret or prevent others from copying its content.

Public queries project only selected fields. They do not include account IDs,
emails, sessions, photo bytes, private game entry IDs, private review text,
lists, or the full collection. Enabled statistics expose aggregate counts,
completion percentage, and average rating. Enabled activity exposes up to three
currently playing entries and three dated completions, including title, platform,
rating, and completion date. Only explicitly published reviews appear in the
review section. Public showcase and activity cards do not
link to private game routes. When available, they link to a public catalog page
using the IGDB ID. See [Public catalog](Public-Catalog.md). Authenticated settings
require a normal, completed-profile session
and CSRF protection; recovery sessions cannot change publication settings.

Public profile photos are available for the limited development trial described
below. The sharing form explains basic content rules. Automated content moderation
is deferred under the owner's public-launch decision of 2026-10-24. It is not
implemented. There is no profile directory or social feed in this increment.

## First configure an isolated development project

1. Open the Supabase dashboard, return to the project list, and select **New
   project**. Use a name such as `vestigium-development`, a generated database
   password, and a nearby region. Store the password privately.
2. Keep the existing Supabase project connected to Vercel **Production**. Do not
   migrate or test against that database during feature development.
3. In the new project's **Connect** dialog, copy the transaction pooler URI and
   substitute its database password locally. Use `sslmode=require`.
4. Find the project's URL and **publishable** API key in its connection/API
   settings. Neither `service_role`, `sb_secret`, nor a JWT signing secret is
   needed by the application.
5. In Vercel **game-backlog → Settings → Environment Variables**, set these values
   for **Preview only**. Check for branch-specific overrides of `develop`.

| Variable | Development value |
| --- | --- |
| `DATABASE_URL` | New project's transaction pooler URI |
| `SUPABASE_URL` | New project's HTTPS URL |
| `SUPABASE_PUBLISHABLE_KEY` | New project's publishable key |
| `SECRET_KEY` | A separate, stable Flask session signing secret |
| `IGDB_CLIENT_ID` | Existing catalog application ID |
| `IGDB_CLIENT_SECRET` | Existing catalog application secret |

Generate a Flask secret locally with `python -c "import secrets;
print(secrets.token_hex(32))"`. Never put database passwords or session secrets in
Git, client JavaScript, or chat. The old `instance/vercel-preview.env` may point to
the shared database: do not import it into the new environment unchanged.

## Supabase Authentication settings

In the **development** project:

1. Enable the Email provider and email/password registrations. Keep email
   confirmation enabled. The application requires a confirmed email.
2. Set Authentication's Site URL to the stable Preview URL followed by
   `/account/login`. For local tests using real Supabase Auth, use the actual
   local application URL. Verify the selected project before saving settings.
3. The standard signup confirmation link can stay in the confirmation email.
   After confirming, users sign in with their email and password. The application
   does not accept tokens from URL fragments as authenticated server sessions.
4. Keep the default **Reset password** email for initial testing. Recovery uses a
   PKCE link bound to the browser that requested it. Open the email link in that
   browser within 30 minutes. The callback exchanges a one-use authorization code
   on the server and removes it from the address bar before showing the password
   form. Access and refresh tokens do not travel in the callback URL.

   After configuring custom SMTP, you may optionally replace the reset email
   with the code-based template below. The application supports both flows.

```html
<h2>Reset your Vestigium password</h2>
<p>Enter this code on the recovery page:</p>
<p><strong>{{ .Token }}</strong></p>
<p>If you did not request this email, you can ignore it.</p>
```

5. Configure SMTP for reliable registration and recovery emails and to customize
   templates where the dashboard requires it. Supabase's
   default mail service is limited and may restrict delivery to organization
   members; verify its current dashboard limits before inviting testers. Provider
   rate limits remain active. CAPTCHA is not integrated in this delivery.

## Apply the development schema explicitly

Configure the same development variables in ignored `instance/config.py` or the
local shell, then run on this feature branch:

```powershell
python -m flask --app wsgi migrate-db
python -m flask --app wsgi check-db
python -m flask --app wsgi run
```

The migrations are transactional and additive. `002_private_accounts.sql` adds
profiles, server sessions, and nullable collection ownership without deleting
existing rows. It requires PostgreSQL 15 or later. Application requests and Vercel
builds never apply migrations. Check the target project before running commands.

After local verification, integrate and publish to `develop` only with explicit
user approval. That publication creates a Preview deployment using the new
variables. Production integration and publication require separate approval.
Both environments need this schema and account configuration before serving the
new version; rollback must use a compatible version, not the old shared app.
Before allowing real accounts in production, retire or protect every older
deployment that still has database access: the old shared application has no
ownership checks. Rotate its database credential as part of the authorized
cutover and give the new credential only to the account-aware deployment. Verify
that old deployment URLs cannot read the new private collections. Simply moving
the production alias does not remove access through historical deployment URLs.

## Preserve the original collection

Old rows initially have no owner and are invisible to signed-in accounts. A new
registration never claims the shared collection automatically. To transfer it:

1. Back up the original database and export its collection before switching
   production versions.
2. Register, confirm your email, and sign in once in the correct environment.
3. Copy your account UUID from **Supabase Authentication → Users**. UUIDs are
   environment-specific; do not reuse a development UUID in production.
4. Inspect the assignment first, then explicitly apply it:

```powershell
python -m flask --app wsgi assign-legacy-collection --user-id YOUR_ACCOUNT_UUID
python -m flask --app wsgi assign-legacy-collection --user-id YOUR_ACCOUNT_UUID --apply
```

Assignment is one transaction and fails rather than silently resolving a list
name conflict. Prefer an empty destination library. JSON backups can alternatively
be imported into the intended signed-in account; ownership and credentials never
appear in exported backups.

## Access model

### Statistics, activity, and long profile reviews

Apply migration `013_profile_activity_sharing.sql` before deploying this follow-up
to either hosted environment. The migration is prepared and tested locally; it
has not been applied to hosted development or production in this increment.
It adds `share_statistics` and `share_activity`, both enabled by default for
existing and new profiles under the owner's 2026-10-25 decision. It does not
change overall public/private visibility, publish photos, or publish reviews.
Private profiles remain inaccessible to visitors.

Edit profile offers independent controls for Gaming statistics and Playing now &
recent completions. Turning either off revokes that public section on the next
request. Legacy submissions without the new controls preserve existing choices;
new forms carry a marker to distinguish unchecked controls from missing fields.
The owner's private workspace remains available regardless of those choices.

Public activity queries project no private entry IDs, notes, or account IDs.
Game links open catalog details; legacy entries without catalog IDs render as
plain activity items. Public aggregate counts use the same game/platform entry
semantics and completion rounding as the owner's statistics.

Profile reviews over 300 characters or three lines use a closed native disclosure
with a whitespace-normalized excerpt of at most 260 characters, visually limited
to three lines. Reading cards use a centered, bounded width with a compact
cover/title/date header and body text aligned beneath it. Read more/Show less
expands or collapses the escaped original text without JavaScript or a storage
change; the expanded close control appears after the full text. Spoiler reviews expose no excerpt
and stay behind a separate closed spoiler disclosure. Private notes never enter
either disclosure.

Public profiles also display reviews their owners explicitly published through
Add game or Edit game. Private notes and library records are never queried to
construct this section. Moderation-hidden and viewer-reported reviews are
excluded, and privatizing the profile revokes public access. Spoilers use a
closed disclosure; reviews are paginated in groups of ten. Catalog titles and
covers are fetched in a cached public metadata batch, with game-ID links if the
provider is unavailable.

`/players` searches current public display names and usernames only. It does not
list profiles before a search, search email addresses, or match reserved former
usernames. Searches require 2–80 characters, return at most 20 public identities
per page, and use a process-local 60-request/minute budget configurable through
`PUBLIC_PLAYER_REQUEST_LIMIT`. Search and profile responses are non-cacheable and
excluded from search-engine indexing. This budget is not a distributed rate limiter.

- The server validates Supabase's current user before each authenticated request.
  It refreshes expiring access tokens while holding a database session-row lock.
- Browser cookies contain a random account session reference, not access/refresh
  tokens, user IDs, passwords, or database credentials. A pending recovery request
  additionally stores a temporary PKCE verifier, its email, and its creation time
  in the signed, HttpOnly cookie. The database stores a hash of the
  reference and the provider tokens. Sessions expire after twelve hours; signing
  out removes the local session even if the provider is unavailable.
- Provider tokens are sensitive server-side database records. RLS with no public
  policies prevents access through anonymous/authenticated Data API roles. Keep
  database credentials and privileged service keys server-only.
- The PostgreSQL owner connection bypasses RLS. Explicit, validated owner
  predicates in Flask are the application authorization boundary. This is not a
  JWT-to-RLS integration. Adding a query requires preserving these predicates.
- Games, lists, counts, duplicate checks, filters, roulette, and backup operations
  are scoped to the verified user. Composite foreign keys reject memberships
  whose non-null owner differs from either referenced row. Legacy null owners
  remain available only to offline administration until assigned.
- Private responses use `private, no-store`; writes use CSRF-protected POST.
  Authentication outages fail closed. Recovery sessions cannot browse a library;
  completing recovery deletes all application sessions for that account. Recovery
  links require the originating browser, the expected email, and a valid one-use
  provider code; missing, expired, replayed, or mismatched requests fail closed.
- Profiles have a display name, an optional bio, and an uploaded avatar or built-in
  silhouette. Public profiles expose only the projection described above and an
  owner-confirmed photo when available. Libraries remain private.
- The first confirmed sign-in opens the profile creator. A blank display name
  identifies unfinished setup; collection routes redirect to the creator until a
  valid name and unique username are saved. Public is selected initially, with a
  Private option available before creation. Existing named profiles open the
  library as usual and retain their current visibility.
- The editor previews the player card as fields change. Saving uses a regular
  CSRF-protected form and redirects after success, with a visible confirmation
  beside the save button. Reloading does not repeat the write. Without JavaScript,
  avatar selection, validation, saving, and confirmation continue to work.

## Verification checklist

Use two disposable development accounts in separate browser sessions. Confirm
registration, email confirmation, login, sign-out, reload, and recovery email/code
delivery. Save each profile and create games/lists. Both accounts may use the same
list name and save the same catalog game independently. Each account must see
only its own statistics, roulette candidates, export, and import results. Trying
the other's game/list URLs must return 404. Anonymous library visits redirect to
login; catalog/JSON requests return 401. Verify the production project receives
no development entries.

Automated tests mock only Supabase Auth; ownership and migrations run against
real, disposable PostgreSQL schemas. Never use a production database URL:

```powershell
python -m pytest --postgres-url YOUR_DISPOSABLE_LOCAL_DATABASE_URL -q
```

References: [password authentication](https://supabase.com/docs/guides/auth/passwords),
[email templates](https://supabase.com/docs/guides/auth/auth-email-templates),
[Auth HTTP API](https://github.com/supabase/auth/blob/master/openapi.yaml).


## Profile photos and limited public sharing

Migration `003_profile_photos.sql` adds a color and an optional photo to each
profile. Apply it to the isolated development database with `flask migrate-db`
before publishing this version to Preview. Production migration requires a
separate authorized release.

The browser accepts JPG, PNG, or WebP sources up to 20 MB and 32 million pixels.
Sources over 2 MB or 12 million pixels are optimized locally before cropping:
resize proportionally to at most 2048 pixels on the longest edge, composite
transparency onto white, and encode a JPEG below 2 MB. Failed preparation keeps
the previous selection. Only the prepared file and crop coordinates are submitted;
the large source is never uploaded. The server still independently enforces its
2 MB, 12-million-pixel, still-image validation. Without JavaScript, those server
limits apply directly to the selected source.
Selecting a photo opens a circular crop preview with drag, arrow-key positioning,
zoom, centering, cancel, and Use photo actions. Only a confirmed photo and its crop
coordinates are submitted. Cancelling a replacement preserves the previous
selection.
The crop dialog's paperclip opens a replacement picker without closing the dialog.
Cancelling that picker or selecting an invalid replacement preserves the current
crop; only a valid decoded replacement resets positioning and zoom. No replacement
is persisted until Use photo and the profile save are confirmed.
The server validates the crop against the oriented source dimensions before
resizing; the original remains subject to the same upload validation.
The default silhouette uses eight preset color swatches instead of the native
color picker.
Pillow validates the decoded format, rejects animation, normalizes orientation,
crops to 256 by 256 pixels, and re-encodes a metadata-free JPEG. Original uploads
are never stored or served. The small normalized photo is stored in PostgreSQL
(maximum 100 KB), so Vercel needs no writable disk or public storage bucket.
The authenticated `/account/profile/photo` endpoint serves only the current
account's photo, with private no-store caching and content sniffing disabled.
Removing a photo restores a silhouette with the selected background color.

Migration `010_public_profile_photos.sql` adds `share_photo`, initially false for
all existing accounts, preserving the original private-photo promise. Saving the
updated profile editor or sharing form confirms photo publication through a
CSRF-protected `publish_photo=yes` marker and a visible notice. There is no extra
checkbox. Older forms that lack the marker do not publish an existing private
photo. Private profiles remain private even after confirmation. No other account's
photo is published by another owner's save or by the migration.

The public page includes only a photo-presence boolean and the current username's
`/players/<username>/photo` URL. This endpoint checks current profile visibility,
photo confirmation, and existence on every request. It returns the same 404 for
hidden, missing, unknown, or old-username photos. Private profiles, removed photos,
and renamed URLs immediately stop serving the image. Public photo responses and
errors use `private, no-store`, `noindex, nofollow`, and `no-referrer`; JPEG responses
also disable content sniffing. Previously downloaded copies cannot be recalled.
On the player card, hovering over the avatar reveals an edit pencil. Clicking it
opens photo upload and background color controls. A Remove photo button appears
only when a photo is present and restores the colored silhouette. The same
native disclosure works with a tap or keyboard; Escape and outside clicks close
it. These controls submit with the profile form, even when the disclosure is
closed. Nothing is persisted until the profile is saved.

These checks validate files, not visual content. On 2026-10-24, the owner approved
public photo uploads for the initial launch and deferred automatic content
moderation, superseding the previous development-only trial restriction. As a
future improvement, integrate
automated moderation before publication: accepted images may be published,
prohibited or uncertain images require replacement, and service failures preserve
the previous image without publishing the candidate. Review provider costs and
image-processing privacy terms before connecting an external service. Allow normal
game, anime, and logo avatars without treating every weapon as prohibited content.
No images are sent to a moderation provider in this increment.


## Profile overview and game showcase

`/account/profile` displays the signed-in player's identity, progress, selected
showcase, currently playing entries, and dated completions. `/account/profile/edit`
contains the name, bio, avatar, and crop editor. New accounts must finish this
editor before browsing their library; successful setup opens the profile overview.
Existing sign-ins still open the library. Previously opened forms posting to
`/account/profile` remain compatible during deployment.

`/account/profile/showcase` lets the owner select up to five distinct library
entries and order them with position fields or move buttons. The selection is
independent of the library's Favorite marker and never changes it implicitly.
Empty positions are skipped; saving five empty positions clears the showcase.
Deleting a library entry automatically removes it from the showcase.

Apply `004_profile_showcase.sql` to the isolated development database before
publishing this version to Preview. It stores ordered slots with a five-position
limit and a composite game/owner foreign key. Replacement happens in a transaction
with an account row lock. Invalid selections preserve the previous showcase.
RLS remains enabled without public Data API policies. All reads and writes use
the verified account for this private overview. The separate public profile
endpoint exposes only the selected projection described above.

Recent completions use recorded completion dates, not guessed activity times.
The Playing section shows up to three entries; collection statistics still cover
all the owner's entries. Empty profiles include guidance for adding a first game.
