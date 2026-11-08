# Grid and game image audit — 2026-11-08

## Pagination and incomplete rows

Search pages now contain 24 results. The other paginated surfaces already use
page sizes divisible by every column count at their responsive breakpoints:

| Surface | Page size | Columns |
| --- | ---: | --- |
| Discover recommendations | 12 | 4, 3, 2, 1 |
| Catalog search | 24 | 4, 3, 2 |
| Owner and public wishlist | 24 | 4, 3, 2, 1 |
| Community player directory | 20 | 2, 1 |
| Connections and public connection lists | 20 | 2, 1 |
| Game and profile reviews | 10 | 1 |

Pagination is applied after the relevant visibility/search filters. Reviews
retain their cards even if catalog metadata cannot be resolved. A final page
may contain fewer cards when results run out; it should not duplicate entries
or fabricate content to fill that row.

The library and personal lists render their full filtered collections without
server pagination. Their final rows can also be incomplete. The five showcase
slots and three featured badges are intentional display limits, not page sizes.
No extra cards or changes to those layouts are needed.

## Image sources

Use IGDB's documented image presets from the fixed, validated CDN host:

- Shared collection covers use `cover_big_2x` (up to 528 × 748), covering the
  library, Discover, search, wishlist, profiles/showcases/reviews, game details,
  personal lists, picker/roulette, and homepage images.
- Autocomplete thumbnails use `cover_small_2x` (up to 180 × 256). Add game
  previews upgrade both legacy small URLs and retina small URLs to the large
  retina cover, including the server-rendered selected-game state.
- Gallery screenshots and game backdrops use `1080p` (up to 1920 × 1080).
  Screenshot strip previews retain the smaller existing rendition. YouTube
  playback and its provider-controlled video quality remain separate.
- Preserve existing lazy loading, dimensions, missing-cover placeholders and
  error fallbacks. No media migration or new image provider is required.

These are maximum rendition sizes. A low-resolution original cannot gain
missing detail by requesting a larger rendition.

Reference: [IGDB image documentation](https://api-docs.igdb.com/#images).
