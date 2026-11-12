# Wishlist

Implemented on `feature/wishlist`, based on develop. Develop publication was
authorized on 2026-10-25. Migrations `015_wishlist.sql` and
`016_wishlist_public_default.sql` are applied to hosted development, with existing
account, library, review, and session counts and profile visibility preserved.
Production remains unchanged. Apply both migrations explicitly before any
separately authorized production deployment. They add an
account-owned table with row-level security and no public API grants, plus
`profiles.share_wishlist`. Migration 016 corrects the initial, unpublished private
default: wishlists are public by default for both existing and new accounts.
This one-time correction does not change overall profile visibility; a private
profile still hides its wishlist. No hosted wishlist choices exist yet. Later
explicit opt-outs persist and are never reset by ordinary visits or repeat
migration runs.
Existing libraries and profile visibility are preserved.

## Saving wishes

An authenticated, completed-profile account can save an unowned catalog game
using Wishlist on its public game page. Wishlisted removes it when selected
again. Saving uses a CSRF-protected POST and server-fetched catalog metadata;
submitted owner IDs, titles, and cover URLs are never trusted. A catalog ID has
one wish per owner, across platforms. Repeated saves are idempotent, and games
already owned on any platform are not added again.

Wishlist records are separate from owned games, lists, ratings, and reviews.
Saving a wish changes no library statistics, showcase, completion history, or
achievement counts. Collection JSON backups retain their existing format and do
not include wishlist entries.

Signed-out visitors can continue through sign-in. Only a validated catalog ID,
timestamp, and allowlisted wishlist intent are carried in the browser session;
no arbitrary return URL is accepted. Sign-in returns to the selected game, where
saving still requires an explicit POST. First-time accounts finish setup and get
a continuation link. Neither viewing a wishlist nor following Add to library
inserts an owned game or silently saves a wish.

## Viewing and sharing

- `/wishlist` redirects to `/account/<current_username>/wishlist` when the
  account has a username. URLs never determine ownership; the session does.
- Owners can search literal title substrings, remove entries, or open the normal
  Add game flow from each cover card. The header contains a Wishlist shortcut.
- Lists are bounded to 500 wishes per account and 24 entries per page, with a
  query limit of 200 characters. The catalog's existing request budget also
  applies to wishlist saves.
- Saved names and validated cover IDs remain readable and removable during
  catalog outages. Browsing a wishlist makes no new catalog metadata requests.
- Edit profile has an initially unchecked **Private wishlist** option.
  Checking it hides the wishlist. It never makes a private profile public. Legacy forms without the
  control marker preserve its existing choice.
- `/profile/<username>/wishlist` is visible only when both the profile and
  wishlist are public. The public profile then displays a Wishlist link.
  Visitors see catalog titles and artwork, never private library fields, owner
  IDs, email addresses, management buttons, or session information.
- Private, hidden, and unknown public wishlists return 404. Former usernames
  redirect temporarily only while the current wishlist remains public. Owner
  visits redirect to their private management page.
- Wishlist responses use `private, no-store` and `noindex, nofollow` so privacy
  changes take effect on the next request and old links are not cached.

## Moving to the library

Add to library reuses the existing full Add game form, including platform, status,
rating, private notes, and explicit public-review publication. The form explains
that saving moves the selected wish into the library. Quick-add from a game page
and successful collection backup imports follow the same rule.

Wishlist removal occurs within the collection write transaction, after a valid
owned entry is inserted. Validation errors, provider failures, duplicate-entry
rejection, and rolled-back saves leave the wish in place. An account-row lock
serializes wish insertion with collection transfer, preventing simultaneous saves
from leaving the game on both sides. Removing an owned entry later does not
silently recreate a wish.

## Validation

Tests use disposable local PostgreSQL schemas and mocked authentication/catalog
responses. Coverage includes owner isolation, CSRF and recovery sessions, signup
and sign-in continuation, public defaults, explicit privacy opt-out and revocation,
aliases, bounded queries/pages/capacity, escaped metadata, catalog failures,
normal and failed library transfer, simultaneous saves, and backup imports.
Local browser previews use fictional accounts and public catalog artwork only.
