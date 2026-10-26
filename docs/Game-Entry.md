# Game entry forms

Add game and Edit game share their identity and field templates and inherit both
theme palettes. A selected game appears above the form with its portrait cover
and name. Catalog-linked names remain fixed; legacy entries retain an editable
title. The Add form keeps the existing catalog combobox, content filter,
keyboard navigation, platform validation, and safe server-resolved metadata.
Selecting a game reveals its cover, collapses the search, and focuses Platform.
Change game reopens the catalog search.

Platform, status, and the existing five-star picker appear together. Review text
and the explicit publication checkbox remain visible in the next block; spoiler
options and existing public-review deletion retain their prior behavior. Dates
and personal stickers are grouped under More details, expanded after server-side
validation errors. Collapsing a section does not disable or omit its values.

The server's save, ownership, duplicate, privacy, and publication rules are
unchanged. This local preview is on `feature/ivory-light-theme` alongside the
reviewed light palette, with no hosted deployment or migration.

Validation covers Add and Edit, catalog selection and stale responses, rating
precision, sticker and date persistence, and public-review publication controls.
Browser checks use only the fictional local preview account.
