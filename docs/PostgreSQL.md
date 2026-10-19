# PostgreSQL migration and Supabase development setup

The application supports PostgreSQL through Psycopg 3 when `DATABASE_URL` is set.
Without that setting, local development continues to use SQLite. This change
prepares persistence for hosting; it does not deploy the application or add user
authentication. Keep the application local until access control is implemented.

Use a dedicated development database for this process. Do not connect these
commands or test runs to a production database. Code changes remain on their
task branch until the user explicitly authorizes integration.

## 1. Preserve the existing collection

If you have an existing collection, export its JSON backup from the current local
application and keep it outside the repository. Stop the local Flask server before
copying `instance/backlog.sqlite` to a safe location as a second backup. The SQLite
file is not deleted or modified by the transfer command.

If this checkout has no collection yet, skip the data transfer steps. An empty
PostgreSQL database is sufficient to start using the application.

## 2. Create a Supabase development project

1. Sign up or sign in at the [Supabase dashboard](https://supabase.com/dashboard).
2. Create an organization if prompted, then choose **New project**.
3. Name the project `game-backlog-development`, choose a suitable region, and save
   the database password in your password manager. Wait until the project is ready.
4. Open **Connect** and select **Transaction pooler**. Copy its PostgreSQL URI.
   This connection supports serverless application requests and IPv4 connections.
5. Replace the password placeholder locally. Percent-encode reserved characters
   in the password when inserting it into a URI. Never share the completed URI,
   database password, secret key, or configuration file in chat or commit them.

Use a separate Supabase project or suitably isolated database branch for future
production. A Git branch does not create an isolated database. No SQL needs to be
pasted into the Supabase SQL Editor: the application's migration command creates
the schema. Use a database-owner connection for migrations and this initial
server-side setup; anonymous API keys are not database connection credentials.

## 3. Install dependencies and configure local secrets

Run these commands in PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Create or edit `instance/config.py` locally, preserving any existing IGDB settings.
Replace the placeholders with your own values:

```python
DATABASE_URL = "postgresql://USER:ENCODED_PASSWORD@HOST:6543/postgres?sslmode=require"
SECRET_KEY = "replace-with-the-generated-secret"
IGDB_CLIENT_ID = "your-client-id"
IGDB_CLIENT_SECRET = "your-client-secret"
```

Use the actual URI from **Connect**; do not guess its username, host, or port.
Keep the secret key stable between restarts. The whole `instance/` directory is
ignored by Git. Environment variables with these same names take precedence over
the local configuration file outside tests, and are the intended hosted setup.
PostgreSQL mode requires an explicit secret key and never generates a secret file.
Remote connections require SSL, and prepared statements are disabled for
Supabase transaction-pooler compatibility.

## 4. Apply the PostgreSQL schema

```powershell
.\.venv\Scripts\python.exe -m flask --app app migrate-db
.\.venv\Scripts\python.exe -m flask --app app check-db
```

Expected output includes `PostgreSQL ready. Applied 1 migration(s).` on the first
run and `PostgreSQL connection and schema check successful.` Repeating
`migrate-db` applies zero migrations and preserves data. Migration files are
versioned and checksummed; never edit a migration that has already been applied.
Failed migrations roll back their schema changes and version records together.
An existing unrelated table with a conflicting name causes failure rather than
being silently adopted or overwritten.

Ordinary PostgreSQL requests do not initialize or migrate the schema. `init-db`
remains the SQLite-only initialization command. If connection checks fail, verify
the project status, URI, encoded password, SSL setting, and network restrictions
locally. Share only the sanitized command result, never credentials.

Tables have row-level security enabled with no client-facing policies. The
server-side database owner can access the collection; browser clients should
never receive the database credentials. This protects direct Data API access,
but does not replace authentication on the Flask application itself.

## 5. Transfer an existing SQLite collection, if present

The source must have the current SQLite schema, including the lists tables.
Older collections should first be initialized with the SQLite application while
`DATABASE_URL` is unset, after making the backups described above. Do not run
initialization against a different file by mistake.

Validate the source without connecting to PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m flask --app app migrate-sqlite --source instance/backlog.sqlite
```

Review the reported game, list, and membership counts. Then copy into the empty,
migrated development target:

```powershell
.\.venv\Scripts\python.exe -m flask --app app migrate-sqlite --source instance/backlog.sqlite --apply
```

The transfer preserves game and list IDs, personal fields, covers, dates, creation
timestamps, and list memberships. It advances identity sequences for subsequent
inserts. It reads the source in a consistent, read-only snapshot and copies all
target data in one transaction. Invalid data or a nonempty target causes failure;
no partial collection is committed. Repeating `--apply` never overwrites a
previous transfer. It does not copy SQLite's internal legacy migration snapshots.

Alternatively, the existing JSON import works on PostgreSQL with its original
add-only merge behavior and 2 MB / 5,000-game limits. JSON import deliberately
does not retain local database IDs. Do not use both methods for the same initial
transfer without first reviewing their different behavior.

## 6. Validate locally before hosting

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Open `http://127.0.0.1:5000` and verify collection counts, statuses, reviews,
ratings, dates, covers, lists, filters, details, and backup export. Add, edit, and
delete a temporary game, then restart Flask and check that the data persists.
Catalog-dependent actions require valid IGDB credentials. Keep the development
server bound to localhost.

To return to SQLite, stop Flask and remove `DATABASE_URL` from the local config
and environment, then restart. The original SQLite file is preserved, but later
PostgreSQL edits are not automatically copied back. Export a JSON backup from
PostgreSQL first if you need to retain those changes.

## Automated regression tests

The default suite uses isolated temporary SQLite databases. Test configuration
ignores the application's real `DATABASE_URL` environment variable:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

To run the same application tests and the PostgreSQL migration tests, configure
`TEST_DATABASE_URL` locally with a dedicated PostgreSQL **test** database URI:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

When `TEST_DATABASE_URL` is present, each relevant test creates and removes its
own random `test_...` schema. The test database user must be allowed to create
schemas. The PostgreSQL-only tests skip when this variable is absent. Never point
this setting at production or share its value. Remove it to return to SQLite
tests. The optional `--postgres-url` flag is convenient only for credential-free
local disposable databases; prefer the environment variable for secret URIs.

## References

- [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase prepared-statement compatibility](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL)
- [Psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [Flask on Vercel](https://vercel.com/docs/frameworks/backend/flask)
