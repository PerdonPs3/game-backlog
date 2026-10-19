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

[Back to the wiki](README.md)
