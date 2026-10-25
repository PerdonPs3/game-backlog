# Roadmap

The long-term idea is a personal gaming library where finishing adventures also
helps your player profile grow. The stages below describe a proposed direction,
not a release schedule. Checked items are implemented; unchecked items are planned.
For the current priority order and release state, see the
[product plan](../Product-Plan.md#current-priorities--2026-10-25).

## Active priorities — 2026-10-25

Production accounts, profiles, public game reviews, catalog media, and the guided
homepage are released. Existing development accounts were copied into production
with their passwords and data preserved; future changes are not synchronized.
Registration/recovery email delivery remains the highest operational priority,
paused while the owner defers provider setup.

Discover improvements are implemented and reviewed locally, awaiting publication
authorization. Public reviews on player profiles plus public-name/username
search are implemented and locally validated; the owner authorized their
develop publication on 2026-10-25. Migration 013 is applied to hosted development. Then prioritize a separate wishlist,
status-aware library suggestions, following, and preference-based catalog
recommendations. A conversational AI layer is a later optional increment with
explicit cost and privacy decisions. Historical unchecked release-validation
items below are not a claim that the production account release is still pending.

- [ ] Publish the reviewed Discover increment after explicit authorization.
- [ ] Validate and publish public profile reviews and public player search.
- [x] Implement a wishlist separate from owned games, public by default with a privacy opt-out and library transfer (develop publication authorized on 2026-10-25; migrations 015–016 applied to hosted development).
- [ ] Extend the library picker with selected statuses and preference signals.
- [ ] Define and implement following, including privacy and abuse boundaries.
- [ ] Add explainable catalog recommendations before an optional AI chatbot.

### 1. Make the collection easier to manage

- [x] Search your own collection by title, alongside the existing status filter.
- [x] Add **On hold** and **Dropped** statuses for paused and abandoned games.
- [x] Record optional start and completion dates to build a personal play history.
- [x] Add a **What should I play next?** picker that randomly suggests a Backlog entry.
- [x] Export and import JSON backups, without overwriting existing entries.
- [x] Organize games into personal lists with cover previews and membership filters.
- [x] Switch between dark/gold and light/purple themes, remembering the selection.
- [ ] Offer English and Spanish interface translations without changing user-written content.
- [ ] Add monthly history charts based on recorded completion dates.

### 2. Find games in a shared catalog

- [x] Search an external game catalog instead of typing every detail manually.
      For example, searching **Resident** would return matching titles to choose from.
- [x] Display covers and release years in suggestions, with available platforms after selection.
- [x] Search title words and aliases with popularity-aware ordering, paginated Explore results, and an official/community content filter based on IGDB types and tags (published to develop).
- [x] Store catalog identifiers and validate the selected game and platform.
- [x] Display game covers in the collection.
- [x] Block duplicate catalog game/platform combinations and link to the existing entry.
- [x] Allow anonymous catalog search and public game detail pages, independent of private library entries.
- [x] Give each catalog game a stable, shareable page URL that opens directly on
      refresh or in a new tab without signing in. Link to it from library covers;
      keep the current modal only as an optional quick view. Never include the
      owner's private notes, rating, or progress in the shared catalog page.
- [x] Connect Explore from the welcome page and library; preserve catalog selection
      through sign-in and profile setup, with explicit confirmation before adding.
- [x] Link public profile showcase games to shared catalog detail pages.
- [x] Add game-specific artwork backgrounds, selectable trailers/screenshots, and a public game-details sidebar.
- [x] Publish reviews explicitly from both Add game and Edit game, with a five-star rating scale, spoiler labels, reporting, and separate private notes.
- [ ] Reuse the same catalog flow from Discover.
- [ ] Validate anonymous search, sharing, and the authenticated add flow in Preview.

Game metadata and covers are provided by [IGDB](https://www.igdb.com/).

### 3. Connect Steam

- [ ] Link a Steam account through Steam's official sign-in flow, without asking
      users to enter their Steam password on this application.
- [ ] Import available library data, with user control over which games to add.
- [ ] Show playtime and achievements where the API and privacy settings allow it.
- [ ] Match imported games to existing entries without overwriting personal
      ratings, reviews, or completion status.

Steam integration will depend on API access and account privacy settings. Importing
a game or detecting playtime will not automatically mark it as completed.
Games from other platforms remain supported through the catalog.

### 4. Build a personal player profile

- [x] Add a private profile with a display name, a short bio, and a built-in avatar.
- [x] Upload profile photos with an adjustable circular crop and preset avatar colors.
- [x] Validate the Obsidian palette pilot on the dark profile before wider adoption.
- [x] Separate a private profile overview from the editor and add an ordered five-game showcase.
- [ ] Validate the overview, showcase ordering, and empty states in Preview before release.
- [x] Show collection statistics: totals, status counts, completion progress, and average rating.
- [x] Implement accounts and separate collections with automated two-account isolation tests.
- [ ] Validate real signup, confirmation emails, recovery, and isolation on the separate Preview database before release.
- [x] Let users choose which supported profile fields and showcase information to make public.
- [x] Implement unique usernames and optional public profile links
      with separate bio, showcase, and photo sharing controls. Existing private uploads require explicit publication.
- [x] Default new profile setup to Public with a Private option, accept uppercase
      username input while keeping lowercase links, and organize sharing controls
      into identity, visibility, and shared-content sections.
- [x] Allow username changes every 30 days, show the next available time, and
      redirect reserved previous names directly to the current public profile.
- [ ] Validate public profile publication, anonymous viewing, and revocation in
      Preview before release. Add reporting and moderation before public photos
      or profile discovery.

### 5. Add progression and customization

- [ ] Earn experience points (XP) for completing games and meeting optional challenges.
- [ ] Explore capped XP rewards based on game length and verifiable achievements,
      once suitable data sources are available.
- [ ] Level up a player profile and unlock customizable avatar frames and other
      cosmetic rewards through levels or milestones.
- [ ] Prevent repeatedly toggling a game's status from granting duplicate completion rewards.

The reward rules are still to be designed. Raw playtime alone should not grant XP:
leaving a game running is not the same as making progress. Manually reported
completions and externally verified achievements will need clear distinctions.

### 6. Automate wiki publication

- [ ] Add a GitHub Actions workflow that publishes changes under `docs/wiki/`
      to the GitHub wiki when they reach `main`, keeping these files as the
      source of truth and mapping the wiki index to `Home.md`.
- [ ] Enable the GitHub wiki and create its first page before the first sync.
- [ ] Store a token with wiki write access as an Actions secret for publication.

### 7. Deploy with Vercel and Supabase

- [x] Deploy the web application on Vercel.
- [x] Use Supabase PostgreSQL as the hosted database, migrating the current
      SQLite schema and data while preserving existing collections.
- [x] Adapt and validate the Flask application for Vercel's runtime and
      Supabase database connections, including persistent data across requests.
- [x] Configure deployment credentials securely and verify the hosted workflow
      before publishing to production, with explicit user approval.

### 8. Prepare for a safe public release

Account features are published to production as well as `develop`. The owner
confirmed production sign-in after the one-time account transfer. Reliable
external registration/recovery email delivery remains pending; see
[account setup](../Accounts.md).

Public access requires accounts, data ownership, and reliable storage. These
requirements take priority over optional integrations and progression.

- [x] Implement registration, sign-in, sign-out, and recovery through Supabase Auth; passwords are managed by the provider.
- [x] Associate games, lists, backups, and statistics with their owning account.
- [x] Enforce ownership on the server: users must never edit or delete another
      user's data, even by changing a URL or submitting a crafted request.
- [x] Add public/private profiles and allow viewing only information the owner
      explicitly shares. Viewing a profile must never grant editing access.
- [ ] Migrate the existing local collection safely into its owner's account.
- [ ] Set up persistent production storage and test backup restoration across
      server restarts and deployments.
- [ ] Configure HTTPS, production sessions, server-only secrets, and a production
      server with debug mode disabled; test authentication and access boundaries.
- [x] Open the production application under the owner's public-launch decision.

### 9. Give the project its own identity

- [x] Adopt **Vestigium** as the project name and **Every game leaves a mark.**
      as its tagline, without renaming the repository or altering existing data.
- [x] Add a minimal, themed welcome screen with a blurred public-cover backdrop,
      the project name, tagline, and links to the library and GitHub. Personal
      collection entries are never used in the welcome screen.
- [x] Add a discreet GitHub link inside the application.
- [x] Build a scrolling product introduction with looping animated library/profile examples, a reduced-motion alternative, and clear account actions (published to develop).
- [x] Add an aggregate activated-account count with a green person icon, minute refreshes, and configurable test-account exclusions (published to develop).
- [ ] Review naming availability before a public launch and add real product
      screenshots to the showcase when the interface is ready.
- [ ] Optionally publish a static project showcase on GitHub Pages, with a
      deployment workflow. Clearly distinguish it from the working Flask app.

GitHub Pages can host a static showcase, not the Python server or writable
database. A public working application requires suitable hosting and the
public-release safeguards above. Keep secrets and real collection data out of
public demonstration bundles.

### 10. Discover releases and updates

- [ ] Add upcoming and recent releases with dates and platform filters.
- [ ] Reuse Discover content in a small homepage preview and link to shared catalog details.
- [ ] Add dated, attributed news only after selecting a suitable source and freshness rules.

[Back to the wiki](README.md)
