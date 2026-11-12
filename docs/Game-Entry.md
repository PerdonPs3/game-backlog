# Game entry forms

Add game and Edit game share their identity and field templates and inherit both
theme palettes. A selected game appears above the form with its portrait cover
and name. Catalog-linked names remain fixed; legacy entries retain an editable
title. The Add form keeps the existing catalog combobox, content filter,
keyboard navigation, platform validation, and safe server-resolved metadata.
Search is always open until a game is selected, without a collapse control.
Selecting a game reveals its cover, hides the search, and focuses Platform.
A separate pencil button beside the selected title reopens the catalog search.
Autocomplete waits 100 milliseconds after typing, coalesces pending requests into
the latest query, and keeps up to 20 recent
query/filter combinations in page memory for two minutes. Refocusing or clicking
the field restores those suggestions without another request; interrupted or
expired searches retry immediately on focus. Refocusing never clears an already
resolved game or platform. Matching recent titles can appear immediately while
the full suggestions refresh. The server uses a bounded indexed autocomplete
query with alias fallback, caches suggestions for five minutes, and retains the
full search for Explore. First-time lookup latency still depends on IGDB.

Platform, status, and the five-star picker appear together. Stars, the numeric
score, and a compact reset control share one row; the reset appears only for a
selected rating. Labels and scores inherit gold or bronze accents from the theme.
Review text
and the explicit publication checkbox remain visible in the next block; spoiler
options and existing public-review deletion retain their prior behavior. Dates
and personal stickers are grouped under More details, expanded after server-side
validation errors. Collapsing a section does not disable or omit its values.

Add and Edit use an illustrated cartography room, with matching day and night
WebP backgrounds and the library's time-of-day theme transition. The backdrop
starts below the measured header height and follows header resizing. The room
assets and complete generation prompts are listed in
[Map-Room-Artwork-Prompts.json](Map-Room-Artwork-Prompts.json).
Navigation between the library and entry pages uses the normal browser behavior.
More details opens and closes with a short height and opacity transition, except
when reduced motion is requested.

Saving an explicitly published review from Add or Edit returns to the owner's
library with a one-time publication confirmation. Publication, ownership,
duplicate prevention, privacy, and atomic saving retain their existing rules.
This change requires no database migration.

Validation covers Add and Edit, catalog selection and stale responses, rating
precision, sticker and date persistence, and public-review publication controls.
Browser checks use only the fictional local preview account.
