# Vercel Preview configuration

The repository includes a Flask WSGI entrypoint and a static asset build for
Vercel. Start with a protected Preview deployment of `game-backlog`, connected to
the Supabase development database. Production publication requires separate
explicit user authorization.

## Application configuration

- `wsgi.py` exports the Flask application as `app` at an entrypoint Vercel detects
  automatically.
- `requirements.txt` provides runtime dependencies. There is no `pyproject.toml`
  dependency source, so Vercel installs the pinned requirements directly.
- `vercel.json` runs `python scripts/build_vercel.py` during the build.
- `.python-version` selects Python 3.14.
- `vercel.json` selects the Flask preset and a 60-second function duration.
- Function execution uses `gru1` (São Paulo), matching the current Supabase
  `sa-east-1` development region to reduce database round-trip latency. Revisit
  this setting if the database region changes.
- The build copies `app/static/` into generated `public/static/` files for CDN
  delivery at the existing `/static/...` URLs. Local Flask development keeps using
  `app/static/`. Do not manually edit the generated copies.
- `.vercelignore` excludes local secrets, SQLite files under `instance/`, test
  artifacts, and development environments from CLI uploads.

On Vercel, configuration comes only from environment variables. Local
`instance/config.py` is not read, and no secret-key file is created. Hosted
session cookies use Secure, HttpOnly, and SameSite=Lax settings. Database
migrations are never run during import, a normal request, or a deployment build.

## Environment variables

In Vercel, open **game-backlog → Settings → Environment Variables** and configure
these server-side variables for **Preview**:

| Variable | Value source |
| --- | --- |
| `DATABASE_URL` | The tested PostgreSQL transaction-pooler URI with `sslmode=require` |
| `SECRET_KEY` | A stable Flask session secret generated independently of Supabase keys |
| `SUPABASE_URL` | The development Supabase project's HTTPS URL |
| `SUPABASE_PUBLISHABLE_KEY` | That same project's publishable API key |
| `IGDB_CLIENT_ID` | The Twitch application's client ID |
| `IGDB_CLIENT_SECRET` | The Twitch application's client secret |

The local file `instance/vercel-preview.env`, when prepared, can be imported
through Vercel's environment-variable import UI. It is ignored by Git and may
contain database credentials: keep it local. Import it only into Preview, then
add missing IGDB settings separately. Do not overwrite unrelated integration
variables or publish these values in documentation, commits, or chat.

The Supabase integration may provide `POSTGRES_URL` and several API keys.
This application reads `DATABASE_URL` explicitly and uses Psycopg, not Prisma
or the Supabase browser SDK. Copy the tested connection setting rather than
blindly renaming a URI containing unsupported `supa` or `pgbouncer` parameters.
Supabase API, JWT, and service-role keys are not needed by this database adapter.
Do not give application secrets a `NEXT_PUBLIC_` prefix.

## Git and deployment settings

1. Set the framework preset to **Flask**, the root directory to the repository
   root, and use the repository's build configuration. Remove stale Next.js or
   other framework overrides if the project previously used them. Do not set an
   output directory override intended for a frontend-only project.
2. Keep `main` as the production branch and use `develop` for integration and
   Preview testing. Keep Preview deployment protection enabled while testing
   account registration and collection isolation.
3. Task branches remain local. Merge into `develop` only after explicit user
   approval, then push `develop` only when publication is authorized. The current
   deployment changes must reach the selected source before a Git-triggered
   deployment can use them. Do not deploy the older production code by accident.
4. After the Preview variables and source are ready, create a new Preview
   deployment so the variables take effect. Do not promote it to production.
5. Verify the deployment before requesting separate production approval. Future
   production needs its own database and independently scoped secrets; never
   point both environments at the same development collection.

## Validation

The development Supabase database must already pass the `migrate-db` and
`check-db` workflow in the [PostgreSQL guide](PostgreSQL.md). A Preview build must
not create or change tables automatically.

Follow [the account setup guide](Accounts.md), including same-browser recovery
links and two-account isolation checks. Preview and Production must reference
different Supabase projects. Hosted startup fails if account configuration is
missing, instead of exposing the previous shared collection.

Check the deployed library, lists, forms, and backup export. Confirm the page is
styled and `/static/style.css`, `/static/theme.js`, and other referenced assets
return successfully. With IGDB configured, search for a game and verify add,
edit, and delete operations using disposable development entries. Reload the
page and verify persistence. Keep production data out of these checks.

Local checks:

```powershell
.\.venv\Scripts\python.exe scripts/build_vercel.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_vercel.py tests/test_database_config.py
```

These checks verify startup without local file writes and the generated assets.
They do not replace an actual Vercel build and Preview request.

## References

- [Flask on Vercel](https://vercel.com/docs/frameworks/backend/flask)
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel environment variables](https://vercel.com/docs/environment-variables)
- [Vercel deployment exclusions](https://vercel.com/docs/deployments/vercel-ignore)
- [Vercel regions](https://vercel.com/docs/regions)
