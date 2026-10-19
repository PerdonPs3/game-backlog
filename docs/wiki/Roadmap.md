# Roadmap

The long-term idea is a personal gaming library where finishing adventures also
helps your player profile grow. The stages below describe a proposed direction,
not a release schedule. Checked items are implemented; unchecked items are planned.

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
- [x] Store catalog identifiers and validate the selected game and platform.
- [x] Display game covers in the collection.
- [x] Block duplicate catalog game/platform combinations and link to the existing entry.

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

- [ ] Add an avatar, a short bio, and a shelf of favorite games.
- [x] Show collection statistics: totals, status counts, completion progress, and average rating.
- [ ] Introduce accounts and separate collections before supporting multiple users.
- [ ] Let users choose which profile information and activity to make public.

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

- [ ] Deploy the web application on Vercel.
- [ ] Use Supabase PostgreSQL as the hosted database, migrating the current
      SQLite schema and data while preserving existing collections.
- [ ] Adapt and validate the Flask application for Vercel's runtime and
      Supabase database connections, including persistent data across requests.
- [ ] Configure deployment credentials securely and verify the hosted workflow
      before publishing to production, with explicit user approval.

### 8. Prepare for a safe public release

Public access requires accounts, data ownership, and reliable storage. These
requirements take priority over optional integrations and progression.

- [ ] Add registration, sign-in, sign-out, secure password storage, and account recovery.
- [ ] Associate games, lists, backups, and statistics with their owning account.
- [ ] Enforce ownership on the server: users must never edit or delete another
      user's data, even by changing a URL or submitting a crafted request.
- [ ] Add public/private profiles and allow viewing only information the owner
      explicitly shares. Viewing a profile must never grant editing access.
- [ ] Migrate the existing local collection safely into its owner's account.
- [ ] Set up persistent production storage and test backup restoration across
      server restarts and deployments.
- [ ] Configure HTTPS, production sessions, server-only secrets, and a production
      server with debug mode disabled; test authentication and access boundaries.
- [ ] Start with a small, controlled release for friends before opening access widely.

### 9. Give the project its own identity

- [x] Adopt **Vestigium** as the project name and **Every game leaves a mark.**
      as its tagline, without renaming the repository or altering existing data.
- [x] Add a minimal, themed welcome screen with a blurred public-cover backdrop,
      the project name, tagline, and links to the library and GitHub. Personal
      collection entries are never used in the welcome screen.
- [x] Add a discreet GitHub link inside the application.
- [ ] Review naming availability before a public launch and add real product
      screenshots to the showcase when the interface is ready.
- [ ] Optionally publish a static project showcase on GitHub Pages, with a
      deployment workflow. Clearly distinguish it from the working Flask app.

GitHub Pages can host a static showcase, not the Python server or writable
database. A public working application requires suitable hosting and the
public-release safeguards above. Keep secrets and real collection data out of
public demonstration bundles.

[Back to the wiki](README.md)
