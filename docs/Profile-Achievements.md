# Profile backgrounds and achievements

This increment is implemented locally on `feature/profile-achievements`.
Migration `014_profile_achievements.sql` must be applied explicitly before any
authorized hosted deployment. It has not been applied to hosted development or
production. It adds cosmetic settings and a persistent, account-owned achievement
table, with row-level security and no grants to public API roles.

## Profile layout

The owner and visitor use the same banner component. The four existing metrics
sit alongside the player's identity on desktop, then move below it on smaller
screens. Existing statistics and overall profile privacy choices remain in force.
Earned badges appear directly below the banner, followed by the existing showcase,
activity, and explicitly published reviews.

Edit profile provides Castle, Aurora, and Obsidian presets and a custom upload.
Aurora and Obsidian are CSS backgrounds. JPG, PNG, and WebP uploads are limited to
2 MB and 12 million pixels, must be still images, and are decoded, centered,
resized to 1600 × 600, composited, and stored as a metadata-free JPEG. The existing
3 MB overall request limit remains in force, including when changing both photos
and backgrounds. No remote image URL is accepted.

Custom image routes check ownership or public profile/background visibility on
every request. Responses use `private, no-store` and `nosniff`. Hiding the
background, choosing a preset, making the profile private, removing the image,
or changing the username immediately revokes its previous public URL. A private
profile is never made public by a customization save.

## Milestones

| Badge | Requirement |
| --- | --- |
| Newcomer | Collect 1 game |
| Collector | Collect 10 games |
| Archivist | Collect 25 games |
| Curator | Collect 50 games |
| Legend | Collect 100 games |
| Finisher | Complete 1 game |
| Completionist | Complete 10 games |
| Reviewer | Publish 1 review |
| Critic | Publish 10 reviews |

Collection/completion counts follow the existing library statistics: each
game/platform entry counts separately. Reviews come exclusively from
`public_game_reviews`, excluding moderation-hidden records at award time. Private
notes and library-only reviews never qualify. Creator remains a separate,
server-assigned cosmetic identifier and cannot be earned or assigned by forms.

Awards are persisted within the same transaction as Add game, Edit game, or backup
import. An account lock and unique owner/key pair prevent duplicate awards.
Previously accumulated progress is reconciled when the owner next opens a page.
Visitor requests do not backfill awards. Deletion, privacy changes, or subsequent
status changes do not revoke a badge already earned.

Initially, the highest earned badge in each category is featured. Owners may
select up to three earned badges, including none, in Edit profile. Selection and
visibility save atomically with profile settings. Old forms that lack the new
control markers preserve these choices. The separate public badge switch hides
the whole badge section. Public badges reveal historical milestones; progress
counts and unlock notifications remain owner-only.

## Unlock notifications

Workspace and library pages show newly earned badges in a themed notification.
Multiple pending milestones share one grouped notice, avoiding a backlog of
popups for existing accounts or large imports. The browser acknowledges only
the current owner's displayed badge keys through a CSRF-protected POST. The
server stores acknowledgement separately from earning; an acknowledged badge
does not reappear on later pages or sign-ins. A failed acknowledgement leaves it
available on a later page.

The notice lasts ten seconds, pauses while hovered or keyboard-focused, and has
a close button and a link to the badge collection. Reduced-motion preferences
disable the entrance and sparkle animation. Small screens place the notification
at the bottom; desktop places it below the site header. No external notification
service, email, or paid provider is used.

## Visual assets

Shield emblems are native SVG in `_achievement_emblem.html`, with amber, teal,
and lavender categories, opaque enamel faces, and contrasting outlines in both
themes. The original Castle artwork is packaged as
`app/static/images/backgrounds/castle.webp` (about 275 KB). It was generated with
the built-in `image_gen` tool, then encoded to WebP for delivery.

Final generation prompt:

> Create a premium panoramic digital matte painting to be used as the DEFAULT
> BACKGROUND IMAGE of a gaming profile header. Landscape 3:1 composition. A
> magnificent medieval stone castle with slender towers on a rocky promontory in
> a mountainous alpine valley, arched old stone bridge crossing the valley, pine
> forests in the foreground, dramatic far mountains and mist, muted sunset opening
> in cloudy sky. Castle right of center; left third mostly dark forest and subtle
> mist so a profile portrait and white text can overlay. Restrained cinematic
> painting, realistic environmental detail, atmospheric depth, subtle warm gold
> sunset balanced against deep blue gray stone and green pine, not oversaturated.
> Clear silhouettes at banner size. No characters, people, logos, writing, UI,
> border or watermark. Edge to edge artwork only. This is an original fantasy
> environment, no recognizable game location.

Feature tests run only in disposable local PostgreSQL schemas. The local preview
uses fictional accounts; it does not copy or mutate hosted account data.
