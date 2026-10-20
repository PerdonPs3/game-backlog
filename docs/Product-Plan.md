# Product direction: profile, public catalog, homepage, and Discover

This is a proposed implementation order, not a release schedule. The dark profile
palette and the private profile overview design are approved in Preview. The
five-game showcase is deployed to develop. Each phase should be
reviewed in Preview before moving to the next one or expanding its scope.

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
scrolling. Search fields and suggestion lists keep their own wheel/keyboard
behavior. Reduced-motion users retain native scrolling without automatic snaps.
Public game selections use a short exit fade and slide, followed by an entrance
on the game detail page. Modified clicks and new-tab targets remain native, and
back/forward navigation resets pending animations. The search focus ring wraps
the complete input and search button. The light-theme wordmark uses the existing
purple palette; dark mode retains the amber wordmark.
