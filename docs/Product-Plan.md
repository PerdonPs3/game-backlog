# Product direction: profile, public catalog, homepage, and Discover

This is a proposed implementation order, not a release schedule. The dark profile
palette and the private profile overview design are approved in Preview. The
five-game showcase is deployed to develop. Each phase should be
reviewed in Preview before moving to the next one or expanding its scope.

## Current priorities — 2026-10-25

This section supersedes the historical execution order and pending-release notes
below. Accounts, profiles, public reviews, the catalog gallery, game details, and
the animated introduction are now in production. The owner confirmed successful
production sign-in after all three existing development accounts and their data
were copied into the previously empty production database. The environments
remain separate; this was not ongoing synchronization.

| Order | Delivery | Current state and reason |
| --- | --- | --- |
| P0 | Reliable registration and recovery mail | Still pending provider setup and real external delivery checks. Paused at the owner's request; do not silently resume Google/Brevo onboarding or purchase a service. Existing confirmed accounts are not time-limited by email quotas. |
| P1 | Finish the Discover increment | Filtered catalog browsing and updates without page reload or scroll reset are implemented and reviewed locally on `feature/discover-catalog`. Await explicit integration/publication authorization; preserve this branch. |
| P1 | Public reviews on profiles and player search | Implemented and locally validated on `feature/community-profiles`. The owner authorized integration/publication to `develop` on 2026-10-25; migration 013 is applied to hosted development. Production remains unchanged. |
| P1 | Profile personalization and milestones | Banner, compact library-style statistics, shield badges, and unlock notifications are implemented and reviewed on `feature/profile-achievements`. The owner authorized develop publication on 2026-10-25; migration 014 is applied to hosted development. Production remains unchanged. See [implementation notes](Profile-Achievements.md). |
| P2 | Wishlist | Implemented locally on `feature/wishlist`: separate catalog wishes, public defaults with a privacy opt-out, saved covers, and atomic transfer through existing Add game flows. Migrations 015–016 are local only; review before integration/publication. See [Wishlist](Wishlist.md). |
| P2 | Improve What should I play? | Reviewed; develop publication authorized on 2026-10-27. Explicit states, Based on your taste and Random pick modes, genre/rating explanations, disclosed random fallbacks, inline roulette reveals, and day/night salon artwork. See [Library suggestions](Library-Picker.md). |
| P3 | Follow players | Published to `develop` with owner authorization on 2026-10-30; migration 017 is applied to hosted development. Public follows, private requests, opt-in shared lists, blocking, and day/night portrait-gallery artwork are included. Production remains separate. Profile reporting, notifications, and a feed remain separate. See [Player following](Player-Following.md). |
| P3 | Broader recommendations | Reviewed locally and approved for develop integration/publication on 2026-10-30 as part of `refactor/navigation-flow`, which preserves `feature/catalog-recommendations` through a `--no-ff` merge. Discover includes explained taste matches, filters, wishlist saves, and day/night courtyard artwork. No migration or new provider. See [Catalog recommendations](Catalog-Recommendations.md). |
| P3 | Consolidate navigation and game destinations | Reviewed locally and approved for develop integration/publication on 2026-10-30: Library / Discover / Community, account settings, canonical URLs, one modern game page with owner-only progress, guarded legacy aliases, shared library controls, exclusive day/night rooms, and directional transitions with rapid-click recovery. Final validation is required before publication; production remains separate. See [Navigation flow](Navigation-Flow.md). |
| P4 | Optional conversational recommendations | Consider a chatbot after preference-based suggestions are useful. Require a no-payment-compatible provider decision, bounded usage, clear data-sharing choices, and graceful fallback. No AI provider or paid service is authorized or configured. |
| Later | Steam import, news, XP, charts, translations, wiki automation | Useful independent follow-ups; lower immediate value than completing the current discovery and community journeys. |

Automated avatar moderation remains a deferred follow-up under the owner's
explicit launch decision below. File validation and existing privacy controls
must remain active. Broader profile reporting and abuse controls need a separate
increment before expanding social interactions.

### Acceptance for the active community increment

- Show already-published reviews on both the owner's profile and its public view,
  including public catalog title/artwork, five-star rating, date, and game link.
- Review cards must never infer public review content from private notes or
  collection ratings. Hidden, deleted, and reporter-hidden reviews stay excluded. A private
  profile hides its publications from visitors immediately.
- Keep spoiler text behind a native disclosure. Bound review pages to ten cards;
  fetch public catalog metadata in one cached batch with a readable outage fallback.
- Default public statistics and bounded recent activity to visible, with separate
  opt-out controls in Edit profile, as requested on 2026-10-25. Preserve overall
  private-profile visibility, photo consent, and explicit review publication.
  Activity links must open public catalog details, never private library entries.
- Collapse long profile reviews into a three-line excerpt with native Read
  more/Show less controls; preserve full escaped text and keep spoilers concealed.
  Migration 013 is required for the new sharing flags and is applied to hosted
  development for the authorized Preview release; production remains unchanged.
- Search current public display names and usernames only, with no initial bulk
  directory, no email lookup, a bounded query/page size, and a process-local
  request budget. Private/unfinished profiles and previous username aliases must
  not become search results.
- Provide keyboard-accessible links, dark/light themes, and narrow-screen layouts.
- Use fictional accounts and a disposable local PostgreSQL schema for tests and
  previews. Never test these changes against hosted development or production.
- Keep implementation local for review. Integration/publication to develop and
  production each require the corresponding explicit authorization.

## Development status — 2026-10-24

The interface, profiles, sharing editor, public reviews, catalog gallery,
game-specific backgrounds, and game-details sidebar are published to `develop`.
Earlier references below to local implementation or pending Preview publication
are historical implementation notes, not the current deployment status. Public
review publication is supported in both Add game and Edit game through shared
controls and validation. Production migration and deployment remain a separate
release operation. The owner-approved public-avatar launch scope is recorded below.

## Public avatar launch scope — 2026-10-24

Public photos are implemented and published to develop. Photos
follow public/private profile visibility, with immediate direct-URL revocation on
privatization, removal, or username changes. Existing private uploads stay private
until their owner saves the updated editor or sharing form after reading the
publication notice. This implementation does not introduce a manual moderation queue.

The owner explicitly approved public registration and photo uploads without
automated image moderation for the initial launch. This supersedes the earlier
moderation release gate. Keep file validation, visibility controls, and explicit
photo-publication consent enabled. File validation does not moderate visual
content; inappropriate images can still be published. No moderation provider,
paid service, or automatic content screening is configured.

**Deferred follow-up:** add automated image moderation
before publication. Allow acceptable images, reject prohibited or uncertain
candidates with an actionable replacement message, and retain the previous photo
if the provider is unavailable. Confirm provider costs and data handling, configure
server-only credentials, test illustrated/game/logo avatars, rate-limit uploads,
and define how existing public photos are checked at activation. The filter must
not claim perfect detection or guaranteed identification of impersonation or
copyright infringement. Do not treat raster decoding/size checks as content
moderation. This remains future work, rather than a condition of the initial
public launch, under the owner's updated decision.

## Interface copy review

### Interface polish from development testing

Implemented locally, pending user review and publication:

- Add game's Official/community filter precedes the title search. Shared select
  chevrons use consistent placement and theme colors.
- Favorite/GOTY distinctions share the library card heading, with top-aligned
  covers. Long reviews have an escaped excerpt and a native keyboard-accessible
  Read more/Show less disclosure; full review text remains unchanged in storage.
- Catalog synopsis/platform panels and profile activity panels size to their own
  content. Platforms use wrapping tags; ratings remain on one line.
- Share supports native sharing, clipboard fallback, cancellation, and a manual
  public-link fallback without sharing query values or fragments.
- Play dates have day/month/year fields plus Today and Clear, retaining the same
  ISO submission and server-side history rules. Invalid or incomplete dates block
  submission. Without JavaScript the existing native date inputs remain available.
- Uploaded portraits use a neutral background beneath the photo, keeping the
  silhouette's chosen color from showing around image edges.

Functional pages use one direct task heading. Remove decorative kickers,
repeated introductions, field-label paraphrases, duplicate tutorials, and
repeated attribution already supplied by the common footer. Keep contextual
privacy boundaries, destructive-action consequences, input limits, actionable
empty states, and live save/error feedback. The homepage retains the brand
tagline and feature demonstrations. This application-wide copy pass is
implemented locally; user review and Preview publication are pending.

## 0. Validate the profile palette

Use the supplied Vestigium Obsidian reference for a profile-only experiment:
`#111317` canvas, `#1a1c1f` cards, `#0c0e11` fields, `#e2e2e6` main text,
`#d7c3ae` secondary text, `#ffc880` primary highlights, and `#f5a623` action fills.
Treat the structured color roles as the source of truth where the prose offers
different shades. Use restrained glows and readable control borders. Preserve
the current light theme, typography, layout, and top-left utility controls.

Acceptance: the profile, avatar menu, crop dialog, and save feedback are readable
on desktop and mobile; other pages retain their current appearance. Broader
palette adoption follows explicit design approval.

The user has approved extending the palette throughout the application. Shared
color roles now cover the homepage and its animated demos, library, public
catalog and game details, account screens, lists, game forms, backups, picker,
and dialogs. Dark mode uses the approved Obsidian surfaces and amber actions;
light mode retains white surfaces and purple accents. Profile refinements
inherit the same roles. Cover artwork, the homepage mosaic, custom avatar
colors, layout, and navigation behavior are preserved. Implemented locally;
user review and Preview publication pending.

The shared header and footer now also frame the library and homepage. Utilities
occupy normal layout space so expanding the GitHub label cannot cover the brand.
The library hero uses a layered poster composition from available collection
covers, with public decorative covers as an empty-library fallback. These images
never add games to the collection. The existing emblem silhouette is preserved
with a brighter metallic finish, including light-theme and favicon variants.

## 1. Make the player profile worth visiting

- Separate a profile overview from the profile editor.
- Add an ordered showcase of up to five games selected from the owner's library.
- Show currently playing games, recent completions, and meaningful statistics
  from existing statuses and recorded dates. Provide useful empty states.
- Add a stable profile identity and a public URL. New profiles default to Public,
  with a Private option during setup; preserve existing privacy choices. Public viewing must expose
  only the selected profile fields and showcase, never account email, tokens,
  private lists, or the entire collection by implication.
- Define the rules for publicly visible uploaded images and reporting before
  opening public profiles broadly. Validate viewing and editing with two accounts.

Start with the private overview and showcase; introduce public visibility as a
separate reviewable step. Progression, XP, social feeds, and comments can follow.

## 2. Build one public catalog and game detail experience

Visitors should be able to search and inspect catalog games without registering.
Create a public catalog detail page that contains game metadata, artwork, and
platforms. Keep it distinct from an owner's private library entry and notes.

Give every catalog game a stable, shareable URL. Opening that URL directly,
refreshing it, or using a new tab must show the same public game information
without signing in. Library covers should provide access to this page. The
current library modal may remain as an optional quick view, but must not be the
only way to inspect a game. Personal notes, ratings, and progress stay private.
This experience is implemented on the public catalog task branch. Private notes
remain available through My entry; catalog-linked covers open the public page.

Reuse this search and detail experience from the homepage, an Explore entry in
the app, and Discover. Keep Add game as a convenient shortcut into the same
catalog flow instead of building another competing search interface.

The primary journey is search -> game detail -> Add to my library. When sign-in
is required, preserve the selected catalog game and return to the add flow after
authentication. Adding always requires the user's confirmation; browsing or
signing in must not silently add games. Bound and cache public catalog requests.

Acceptance: anonymous users can browse catalog data, private collection routes
remain protected, and a signed-in user can add a selected game without repeating
the search or creating duplicate game/platform entries.

## 3. Turn the homepage into a guided product introduction

Build a normal scrolling page with section links and restrained transitions:

1. A clear promise, a public game search entry, Create account, and Sign in.
2. A real library screenshot explaining organization and progress tracking.
3. A real profile screenshot explaining the showcase and player identity.
4. A short three-step explanation: find a game, add it, track your progress.
5. A small upcoming-release preview that opens the shared Discover experience.
6. A final registration action.

Capture examples from a dedicated demo account with fictional or explicitly
approved data. Keep screenshots synchronized with the actual product. Maintain
normal browser scrolling inside the introduction, keyboard access, and reduced-motion preferences.
The cover advances to the introduction after downward wheel intent, PageDown, or
a vertical swipe; only the cover transition is guided.

Treat a user count as a secondary enhancement. Define whether it means confirmed
accounts or completed profiles, use a real server-side aggregate, exclude test
accounts, and never send user records to the browser to calculate it. The wording
must match the chosen definition; do not invent numbers or imply online activity.

## 4. Add a focused Discover section

Begin with upcoming and recent releases, release dates, platform filters, and
links to the same catalog detail pages. A homepage preview and an in-app Discover
entry should reuse the same content and components.

Add news in a later increment after selecting a suitable source, freshness rules,
and attribution. Show original dates and links; distinguish announcements from
confirmed release dates. Avoid starting with an unmaintained general news feed.

## Next concrete delivery

The scrolling homepage is implemented on `feature/scrolling-homepage` for review.
It preserves the existing animated cover background and reuses the public catalog
picker. A shared homepage header separates the top-left appearance controls from
account actions. Visitors see Sign in and Create account; the final invitation
says Start your collection, while signed-in members see Open your library.
A gradient blends the hero into the page, and supported browsers reveal sections
as they enter view; reduced-motion preferences keep the content static.
Library and profile sections use illustrated product sequences with public covers
and fictional example content, followed by three steps and account-aware actions.
The library example moves a game from Backlog to Playing to Completed; the profile
example reveals a five-game showcase. Each sequence plays once when it enters view,
with pause and replay controls. Offscreen and hidden-tab playback stops, while
reduced-motion preferences and unavailable JavaScript retain a static final example.
These illustrations do not read or modify account data.
No production data, database migrations, external counters, or future integrations
are introduced. Desktop and 390 px mobile layouts, light and dark themes, section navigation,
and anonymous search have been checked locally. Preview validation follows
authorized integration into develop and publication.

## Public community count

The homepage person icon reports activated player accounts: profiles created after
verified-email authentication, counted once per identity, including private or
unfinished profiles. It does not count pending sign-ups, online visitors, or every
Supabase Auth row. Deleted application profiles cease contributing; this is not
an audit of deleted provider accounts. No user records are returned to visitors.
The server uses COUNT(*) with a 60-second process-local cache; visible pages poll
once a minute. Changes can take up to two minutes to appear. Zero is displayed
only after a successful count; unavailable totals hide the badge. Offline mode
has no population and hides it too.

Optional server variable PUBLIC_MEMBER_COUNT_EXCLUDED_IDS accepts comma-separated
account UUIDs to omit explicit demo/test identities. Production and development
populations are separate because their databases are separate. Local preview uses
an isolated PostgreSQL schema and fake accounts, so its count is demonstration
data, not the production total. No new database migration or privileged Supabase
API key is required.

## Navigation motion refinement

The cover uses a one-screen advance into the introduction, followed by free
scrolling. Scrolling upward near the introduction's top smoothly returns to the
cover; deeper sections retain native scrolling in both directions. Keyboard and
vertical touch gestures support the same boundary transition.
Document-wide CSS snapping is disabled so the browser cannot add a
second alignment movement near section boundaries. Search fields and suggestion lists keep their own wheel/keyboard
behavior. Reduced-motion users retain native scrolling without automatic snaps.
Public game selections use a short exit fade and slide, followed by an entrance
on the game detail page. Modified clicks and new-tab targets remain native, and
back/forward navigation resets pending animations. The search focus ring wraps
the complete input and search button. The light-theme wordmark uses the existing
purple palette; dark mode retains the amber wordmark.

## Account usability follow-up queue

Resolve and review these increments in order:

1. Registration: password visibility controls, required confirmation validated on
   the server, and a live character count explaining the 8–128 character range.
   Implemented locally; user review and Preview publication pending.
2. Avatar editing: hide silhouette color controls while an uploaded photo is in
   use; restore them when the photo is removed. Implemented locally for saved
   photos and confirmed crops, retaining the selected silhouette color. User
   review and Preview publication pending.
3. Profile setup: display name first, then username, then bio. Suggest a username
   from the display name without overwriting a manual choice; validate uniqueness
   on save and preserve existing username-change rules. Implemented locally;
   user review and Preview publication pending.
4. New-account navigation: finish setup on the created profile, including when
   registration began from a catalog game. Offer an explicit continuation to the
   selected game instead of automatically opening Add game after setup.
   Implemented locally and validated with a new demo profile; Preview pending.
5. Account URLs: introduce username-based library and private profile routes with
   compatibility redirects. A username in a URL must never grant access to another
   account's private collection or editor; retain separate public profile routes.
   Implemented locally, including editor, showcase, and sharing subpages, legacy
   form/JSON compatibility, and owner-only redirects from previous usernames.
   User review and Preview publication pending.
6. Profile sharing design: review the light-theme screen against the user's
   reference. Reduce the heavy lavender section fills, improve spacing and visual
   hierarchy, and present the public profile URL as a readable link rather than
   a code-like fragment. Review username cooldown messaging and alignment of the
   identity, visibility, shared-details, and save controls. Implemented locally:
   white cards, restrained selected-option tints, an address row instead of code,
   a single cooldown date, and aligned section labels. Existing sharing behavior
   is retained; user review and Preview publication pending.
7. Workspace frame: keep the header visible while scrolling and place the footer
   at the end, pushed to the viewport bottom on short pages. The footer must not
   remain fixed over the form. The full-width header aligns the brand beside the
   left utility controls and account actions at the right edge. Implemented locally following the user's choice;
   Preview validation pending.
