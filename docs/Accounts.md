# Private accounts and isolated environments

Hosted PostgreSQL installations require Supabase Auth. SQLite remains an offline,
single-user mode. Account pages are under `/account`; `/` remains public.

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
- Profiles have a display name, an optional bio, and a built-in avatar. Profiles
  and libraries are private; public profiles and uploaded avatars are future work.
- The first confirmed sign-in opens the profile creator. A blank display name
  identifies unfinished setup; collection routes redirect to the creator until a
  valid name is saved. Existing named profiles open the library as usual. No
  schema migration or reset of existing profiles is required for this behavior.
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
