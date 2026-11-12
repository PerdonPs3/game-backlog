# Global release — 2026-11-12

The owner authorized integration and publication of the reviewed development
increment to both `develop` and `main`, including Help and the service-health
workflow. This authorization includes the additive schema updates required by
the production application. Existing development and production accounts remain
separate; this release does not copy accounts or collections between them.

## Included behavior

- Updated Library, Add/Edit game, profile settings, public profiles, Community
  and Discover navigation, day/night scenes, and shared light-theme colors.
- Profile public reviews, privacy controls, backgrounds, featured achievements,
  wishlist, following, private follow requests and blocking.
- Library roulette and preference-based recommendations, catalog popularity,
  rating and release sorting, complete pagination and larger cover images.
- Inline wishlist saves, preserved scroll positions and consistent Next controls.
- Searchable authored Help and a database-backed health check every six hours
  for both hosted environments, without database credentials in GitHub Actions.

## Deployment requirements

Apply migrations 013–017 to production before publishing the new application.
Development already has these migrations. Validate immutable checksums and
existing profile, game, public-review and session row counts before and after
the transaction. No destructive migration or account transfer is part of this
release.

Hosted schema preparation completed on 2026-11-12: development required no
changes; production applied all five migrations transactionally. Immutable
checksums matched and existing profile, game, public-review and session row
counts were preserved.

Run the Python and JavaScript suites, integrate the task branch into `develop`
with `--no-ff`, publish and check Preview, then integrate `develop` into `main`
with `--no-ff`. Preserve all task branches. Verify both deployments and run the
health workflow triggered by its first publication to each branch.

Scheduled checks reduce inactivity risk; they do not resume a paused project
or guarantee uptime. See [Service health](Service-Health.md).

Registration and recovery SMTP setup, automated image moderation, chatbot,
profile reporting and notifications remain separate follow-ups. No paid
service is introduced by this release.
