# Illustrated library preview

The collection screen uses an illustrated archive interior with separate night
and daylight artwork. Its palette is scoped to `body.library-archive` in
`app/static/library-archive.css`; profile, catalog, account, and landing pages
keep their existing themes. The normal theme switch selects the matching
background without introducing a separate preference.

The light palette uses ivory surfaces, espresso text, walnut secondary text,
bronze outlines, and honey-gold primary actions. The dark palette uses walnut,
charcoal, cream text, and gold. Nearly opaque panels keep controls and personal
notes readable over the decorative background. Background art is ignored by
assistive technology and does not intercept input. One existing vector brand
symbol sits on the fabric banner; the large repeated wordmark and floating logo
have been removed from the hero.

Cards keep the original full-width horizontal layout, complete portrait covers,
and detailed notes; on phones they retain their original stacked layout. Shelf
keeps portrait covers in a grid, with four columns on desktop and two on phones. Both views retain the existing filtering, sorting, saved layout,
details, editing, and deletion controls. Cards retain library notes and dates;
Shelf retains its existing compact behavior.

Packaged assets:

- `app/static/images/backgrounds/library-night.webp` (about 380 KB).
- `app/static/images/backgrounds/library-day.webp` (about 429 KB).

Both were generated individually with the built-in imagegen tool from the
user-approved mockups. They are encoded to WebP at the original 1536 × 1024
dimensions. No application UI or game covers are baked into the backgrounds.
The complete prompts and source filenames are recorded in
[Library-Artwork-Prompts.json](Library-Artwork-Prompts.json).

Validation uses fictional local accounts and disposable local PostgreSQL
schemas. This preview does not require a database migration or hosted changes.
