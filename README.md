# Game Backlog

A personal video game tracker built with Python, Flask, and SQLite. Keep track of
what you want to play, what you are playing, and what you have finished, with
optional ratings and reviews.

Built as a learning project focused on server-rendered pages, SQL persistence,
input validation, and automated testing.

## Features

- Add, view, edit, and delete games.
- Create and rename personal lists, include a game in several lists, and filter the library by list alongside search and status. Removing a list never removes its games.
- Preview each list with a stack of its covers; switch the editor between All games and In this list. Saving stays in the editor with confirmation and preserves the selected view.
- New JSON backups include lists and their memberships; old backups still work. Imports merge same-named lists additively without removing existing memberships or replacing personal game data.
- Track a title, platform, and status: **Backlog**, **Playing**, **Completed**, **On hold**, or **Dropped**.
- Record optional start and completion dates; clear them by leaving the fields empty.
- Mark personal Favorite and Your GOTY stickers when adding or editing; both can be selected independently.
- Pick a random game from the entire Backlog without changing its status.
- Narrow random picks by your saved platform and catalog genre. Preferences are combined, and Pick again keeps them. Unknown genres stay eligible only with Any genre; catalog outages never silently ignore a selected genre.
- Choose preferences first: opening the picker does not draw a game until you press Find my next adventure.
- Reveal random picks with a three-second cover roulette, or skip straight to the result. A single match gets a short reveal; reduced-motion settings and browsers without animation support show the result directly. The animation never changes the server's random selection.
- Enable optional, quiet roulette ticks and a reveal chime, synthesized locally in your browser. Sound starts muted; your preference is remembered, but browser autoplay restrictions may require clicking Enable sound again.
- Export a portable JSON backup and import new entries without overwriting existing games.
- Search the collection by title and filter by status.
- Sort the collection by recently added, oldest added, title (A–Z), or highest rating; unrated games appear last when sorting by rating.
- Update collection results automatically while typing or changing status, without reloading the page.
- View global collection counts, completion progress, and the average of rated games above the filters.
- Choose new games from IGDB suggestions with covers and release years.
- Display saved covers beside collection entries, with a fallback when no cover is available.
- Switch between detailed cards and a cover-focused shelf; your browser remembers the view while search, sorting, and filters keep working. Open a cover or title for the full review and dates.
- Open a game's cover or title to view its synopsis, genres, first release date, and personal notes in an accessible dialog. A regular details page works without JavaScript; catalog outages never hide your saved notes.
- Suggestions prioritize exact titles, then title prefixes, with newest releases first within each group.
- Choose a platform from the selected game's available platforms, including linked ports.
- Validate catalog IDs and game/platform combinations on the server.
- Prevent adding the same catalog game twice on the same platform, including when editing.
- Add an optional whole-number rating from 1 to 10 and a review of up to 2,000 characters.
- Clear an existing rating or review by leaving its field empty when editing.
- Preserve entered form values when validation fails.
- Confirm deletion before permanently removing a game.
- Confirm deletion in a small accessible dialog without leaving the collection (with a separate-page fallback without JavaScript).
- Store the collection locally in SQLite, including across server restarts.
- Use a dark interface with gold accents and wrapping for long text.
- Switch between the original dark/gold design and a warm-white/purple light theme on every page. Your browser remembers the choice; before you choose, the app follows your system theme. Covers and personal data are unchanged.
- Use a consistent dashboard-inspired workspace for adding, editing, deleting, importing, and picking games.

## Tech stack

- **Python and Flask** for routes and application logic.
- **SQLite** for persistence through Python's built-in `sqlite3` module.
- **Jinja, HTML, and CSS** for server-rendered pages and styling.
- **Flask-WTF** for CSRF protection on forms.
- **pytest** for automated tests.

## Run locally

The commands below use **Windows PowerShell**. The project has been tested with
**Python 3.14.3**. Install Python and Git before starting, and make sure the
`python` and `git` commands are available in your terminal.

### 1. Clone the repository

```powershell
git clone https://github.com/PerdonPs3/game-backlog.git
cd game-backlog
```

### 2. Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `python` opens the Microsoft Store or is not found, use the path to your
installed Python executable instead when creating the environment.

These instructions call the virtual environment's Python directly, so activating
the environment is optional and no PowerShell execution-policy change is needed.

### 3. Initialize the database

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
```

This creates the `games` table if it does not already exist. Existing games are
preserved. Older tables receive missing catalog, cover, and play-history columns.
When upgrading the old three-status constraint, the application copies entries
into the expanded table inside a transaction and retains the original as
`games_before_status_upgrade`. IDs, personal reviews, ratings, and creation dates
are preserved. This internal snapshot is in the same database file: it is not a
substitute for exporting a backup to another location.

The application uses `instance/backlog.sqlite` for local data and generates a
local secret key in `instance/secret_key`. The `instance/` directory is excluded
from Git. Do not commit or share the secret key.

### 4. Configure IGDB

Register a confidential application in the Twitch Developer Console, then create
`instance/config.py` locally:

```python
IGDB_CLIENT_ID = "your-client-id"
IGDB_CLIENT_SECRET = "your-client-secret"
```

Never commit this file or share its contents. Credentials and access tokens stay
on the server. Check the connection with:

```powershell
.\.venv\Scripts\python.exe -m flask --app app check-igdb
```

New games require a catalog selection and an available platform. Search results
exclude editions, packs, bundles, and separate port entries; remakes and remasters
remain distinct games. Platforms from linked ports are included in the selected
game's platform dropdown. Results depend on IGDB's available metadata.

### 5. Start the development server

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the terminal running
while using the application; press **Ctrl+C** to stop the server.

The Flask development server and debugger are for local development only. Do not
expose them publicly or use them as a production deployment.

## Run the tests

Install the development dependencies, which also include the application dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The Python suite covers CRUD, filters and sorting, statistics, duplicate
prevention, play-history validation, new statuses, random selection, backup
validation and round trips, CSRF protection, HTML escaping, catalog errors,
strict game/platform selection, and preservation of legacy data. Catalog
requests are mocked; tests never contact IGDB.

If Node.js is installed, also run the dependency-free interaction tests:

```powershell
node --test tests/catalog-search.test.cjs tests/collection-filters.test.cjs tests/cursor-glow.test.cjs tests/delete-confirmation.test.cjs tests/game-details.test.cjs tests/collection-view.test.cjs tests/shelf-covers.test.cjs tests/adventure-roulette.test.cjs tests/roulette-sound.test.cjs tests/list-editor.test.cjs tests/theme.test.cjs
```

Each test uses a separate temporary SQLite database rather than the real
collection. CSRF protection remains enabled during the tests. These tests check
server behavior and rendered HTML; they do not check browser layout visually.

## Project structure

```text
game-backlog/
├── app/
│   ├── __init__.py       # Application factory and configuration
│   ├── catalog.py        # Server-side IGDB client and catalog normalization
│   ├── backups.py        # Portable backup format and strict local validation
│   ├── game_fields.py    # Shared statuses and play-history validation
│   ├── db.py             # Database connection lifecycle and init-db command
│   ├── routes.py         # Collection, forms, validation, and CRUD routes
│   ├── schema.sql        # SQLite table definition
│   ├── static/
│   │   ├── style.css
│   │   ├── collection-covers.js
│   │   ├── collection-filters.js
│   │   ├── cursor-glow.js
│   │   ├── delete-confirmation.js
│   │   └── catalog-search.js
│   └── templates/
│       ├── index.html
│       ├── create.html
│       ├── edit.html
│       ├── delete.html
│       ├── import_backup.html
│       ├── pick.html
│       ├── _brand_easter_egg.html
│       ├── _collection_summary.html
│       ├── _game_collection.html
│       ├── _game_stickers.html
│       ├── _workspace_base.html
│       └── _play_dates.html
├── tests/                # Python regression and dependency-free JS interaction tests
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Current scope

This is a **single-user local application**, not a hosted multi-user service.
It has no account system. New games must be chosen from IGDB; existing manual
entries remain editable. Cover identifiers are saved when adding or editing a
catalog game. Existing catalog entries receive their cover the next time they are
saved from Edit game. Old manual entries without an IGDB ID show a placeholder.
Opening the collection does not make catalog API requests; cover images are loaded
by the browser from IGDB's image host and require an internet connection.

## Backups and play history

- Use **Export backup** in the collection toolbar to download all entries, not
  just the currently filtered results. The JSON includes personal ratings and
  reviews, statuses, dates, catalog IDs, and cover identifiers. It excludes local
  row IDs, credentials, CSRF tokens, and image files.
- Favorite / Your GOTY stickers are included in new exports. Older version-1
  backups without these optional fields remain supported and default to unmarked.
  Your GOTY is a personal distinction, not an official award or a year-based ranking.
- Keep the downloaded file somewhere safe. GitHub stores the application code,
  not your collection or database.
- Use **Import backup**, select the JSON file, and confirm adding new entries.
  The file is limited to 2 MB / 5,000 entries and is validated in full before any
  writes. Invalid files are rejected without partial imports. Files are read in
  memory, not saved to an upload directory.
- Import is **add-only**, not a replacement: matching catalog ID/platform pairs
  are skipped, including duplicates inside the file. Manual entries are compared
  with other manual entries by title/platform; they are not automatically matched
  to catalog entries. Existing ratings, reviews, and statuses are never overwritten.
- Import only your own trusted exports. Catalog metadata is restored offline;
  it is not reverified against IGDB. New entries added through **Add game** still
  require catalog validation. Imported catalog entries are checked against IGDB
  when edited, just like other catalog entries.
- Dates are optional and use YYYY-MM-DD. A completion date cannot precede a known
  start date. Changing status never invents or erases dates, so you can keep a
  prior completion date while replaying a game. Monthly history charts remain a
  future feature.
- **What should I play?** chooses from all Backlog entries, regardless of active
  filters. Playing, Completed, On hold, and Dropped entries are excluded. The
  suggestion does not mark a game as started.
- Completion progress still divides completed entries by the entire collection,
  including On hold and Dropped entries. Their counts appear below the four
  main statistic cards when present.

## Roadmap

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
