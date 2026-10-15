# Game Backlog

A personal video game tracker built with Python, Flask, and SQLite. Keep track of
what you want to play, what you are playing, and what you have finished, with
optional ratings and reviews.

Built as a learning project focused on server-rendered pages, SQL persistence,
input validation, and automated testing.

## Features

- Add, view, edit, and delete games.
- Track a title, platform, and status: **Backlog**, **Playing**, or **Completed**.
- Search the collection by title and filter by status.
- Update collection results automatically while typing or changing status, without reloading the page.
- View global collection counts, completion progress, and the average of rated games above the filters.
- Choose new games from IGDB suggestions with covers and release years.
- Display saved covers beside collection entries, with a fallback when no cover is available.
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
preserved. On connection, older tables receive nullable `igdb_id` and `cover_image_id` columns so
legacy entries continue to work without requiring a catalog match.

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

The Python suite covers creation, editing,
deletion, filtering, optional ratings and reviews, invalid input, missing games,
CSRF protection, HTML escaping of reviews, catalog errors, strict game/platform
selection, and preservation of legacy data. Catalog requests are mocked.

If Node.js is installed, also run the dependency-free interaction tests:

```powershell
node --test tests/catalog-search.test.cjs tests/collection-filters.test.cjs
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
│   ├── db.py             # Database connection lifecycle and init-db command
│   ├── routes.py         # Collection, forms, validation, and CRUD routes
│   ├── schema.sql        # SQLite table definition
│   ├── static/
│   │   ├── style.css
│   │   ├── collection-covers.js
│   │   └── catalog-search.js
│   └── templates/
│       ├── index.html
│       ├── create.html
│       ├── edit.html
│       └── delete.html
├── tests/
│   ├── conftest.py        # Fixtures, temporary databases, and form helpers
│   ├── test_games.py
│   ├── test_catalog.py
│   ├── test_catalog_selection.py
│   ├── test_collection_covers.py
│   └── catalog-search.test.cjs
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

## Roadmap

The long-term idea is a personal gaming library where finishing adventures also
helps your player profile grow. The stages below describe a proposed direction,
not a release schedule. Checked items are implemented; unchecked items are planned.

### 1. Make the collection easier to manage

- [x] Search your own collection by title, alongside the existing status filter.
- [ ] Add **On hold** and **Dropped** statuses for paused and abandoned games.
- [ ] Record start and completion dates to build a personal play history.
- [ ] Add a **What should I play next?** picker that suggests a pending game,
      either randomly or based on selected filters.
- [ ] Export the collection as CSV or JSON so users can take their data with them.

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
