# Illustrated library preview

The collection screen uses an illustrated archive interior with separate night
and daylight artwork. Its palette is scoped to `body.library-archive` in
`app/static/library-archive.css`; profile, catalog, account, and landing pages
keep their existing themes. The normal theme switch selects the matching
background without introducing a separate preference.

The night illustration is a lighting edit of the daylight room: the left window
shows a moon, stars, and dark mountains; cool moonlight replaces sunbeams while
the existing candles retain their warm glow. Both images load as decorative
layers before switching. The library uses a 2.2-second view-transition crossfade
with an opaque old frame, avoiding a dip to black. Browsers without view
transitions fade the daylight layer with CSS instead. Reduced-motion preferences
disable both animations. Other screens retain their normal theme transition.

The light palette uses ivory surfaces, espresso text, walnut secondary text,
bronze outlines, and honey-gold primary actions. The dark palette uses walnut,
charcoal, cream text, and gold. Nearly opaque panels keep controls and personal
notes readable over the decorative background. Background art is ignored by
assistive technology and does not intercept input. One existing vector brand
symbol sits on the fabric banner; the large repeated wordmark and floating logo
have been removed from the hero.

The compact hero uses a plain interface heading aligned with the filters,
with warm yellow-gold text at night and a deeper gold for daylight contrast.
The filters begin 20 pixels below the heading, without a fixed-height hero gap.
It omits the tagline and keeps the primary add action
beside a quieter, translucent recommendation action in both themes.
The add button uses a bronze finish with an inset book icon and a directional
arrow. The recommendation button uses the same proportions with a compass icon;
hover movement respects reduced-motion preferences. These two actions sit below
the filters, to the left of the list, backup, and view controls. The live game
count remains at the start of that toolbar, immediately beside the two actions.
One shared tray aligns all controls to a 44-pixel height, with consistent corner
radii and spacing. The primary group stays on the left and collection utilities
stay on the right, wrapping as groups when the available width is smaller.
All neighboring controls use the same half-rem gap; primary actions expand to
use spare width rather than leaving a large gap between groups.

Cards keep the original full-width horizontal layout, complete portrait covers,
and detailed notes; on phones they retain their original stacked layout. Shelf
keeps portrait covers in a grid, with four columns on desktop and two on phones. Both views retain the existing filtering, sorting, saved layout,
details, editing, and deletion controls. Cards retain library notes and dates;
Shelf retains its existing compact behavior.

Packaged assets:

- `app/static/images/backgrounds/library-night.webp` (about 325 KB).
- `app/static/images/backgrounds/library-day.webp` (about 429 KB).

The daylight room was generated with the built-in imagegen tool from the
user-approved mockups, then edited into the matching moonlit room. Both are
encoded to WebP at the original 1536 × 1024
dimensions. No application UI or game covers are baked into the backgrounds.
The complete prompts and source filenames are recorded in
[Library-Artwork-Prompts.json](Library-Artwork-Prompts.json).

Validation uses fictional local accounts and disposable local PostgreSQL
schemas. This preview does not require a database migration or hosted changes.
