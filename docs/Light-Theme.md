# Ivory light theme

The light theme shares the library's ivory, espresso, bronze, and honey-gold
palette across the homepage, catalog, game details, account forms, profiles,
player search, personal lists, wishlist, picker, and backup screens.

The shared roles are defined in `app/static/light-theme.css`: canvas `#f5f0e6`,
panel `#fffdf7`, text `#30271f`, secondary text `#6d5845`, bronze accents
`#80541f`, and gold actions `#edb646` with dark `#30200d` labels. Page-specific
overrides use matching warm surfaces, outlines, shadows, and logo gradients.
Success, error, status, avatar, and achievement colors retain their meanings.

Changes are scoped to light-mode selectors. Theme storage, transitions, reduced
motion, dark palettes, page structure, and the illustrated library remain intact.
This increment is a local preview on `feature/ivory-light-theme`; it requires no
database migration and has not been published to develop or production.

Validation includes the existing theme behavior and contrast checks, page-shell
tests against disposable local PostgreSQL schemas, and browser inspection of
desktop and mobile layouts using a fictional local account.
