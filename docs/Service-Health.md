# Service health

The Service health workflow checks development and production every six
hours, at minute 23 UTC. It uses the existing `/community/member-count` endpoint, which
performs a real database read and returns 503 when the database cannot be queried.
The endpoint caches its aggregate for 60 seconds, far shorter than this schedule.
Checking a static homepage alone would miss database outages.

Changes to the workflow or probe also run a check on publication to `develop`
or `main`. This verifies the initial installation without waiting for the next
scheduled run. Subsequent scheduled checks execute only from `main`.

The probe has a 15-second request timeout, up to three attempts, short backoff,
no redirects, and bounded JSON parsing. It requires a successful status and a
valid nonnegative count; HTML login pages, null counts and failures are unhealthy.
It does not write data, print counts or credentials, create accounts, send mail,
or need database/API secrets. A failed run appears in GitHub Actions; native
notification delivery depends on the owner's GitHub notification preferences.

## Activation and limits

- The repository is public. Standard GitHub-hosted runners are currently free
  for public repositories; this workflow uses a standard Ubuntu runner.
- Scheduled workflows execute from the repository's default branch, currently
  `main`. The owner authorized publication to both branches on 2026-11-12 as part
  of the [global release](Global-Release-2026-11-12.md). The schedule starts only
  after the workflow is published to `main`; its copy in `develop` does not
  create a second scheduled job. Do not change the default branch to bypass
  publication requirements.
- Supabase may pause free projects with low database activity over a week.
  Periodic readiness checks produce database activity and can reduce inactivity,
  but do not guarantee immunity from pausing, platform outages, or quota limits.
- The probe cannot resume an already paused project. Confirm its status in
  Supabase and use Resume project when needed; no paid plan is requested.
- GitHub may delay scheduled runs and automatically disables schedules in public
  repositories after 60 days without repository activity. Review failed runs and
  keep the schedule enabled; this is not a permanent availability guarantee.

Run manually without secrets:

```powershell
python scripts/check_service_health.py https://game-backlog-git-develop-maxis2.vercel.app
```

References: [Supabase pausing](https://supabase.com/docs/guides/platform/free-project-pausing),
[GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[runner billing](https://docs.github.com/en/actions/concepts/billing-and-usage).
