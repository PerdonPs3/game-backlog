# Public game reviews

Catalog game pages show opt-in player reviews with a five-star rating, author,
profile link, date, and paginated text. Public reviews are separate records from
private collection entries. Creating, editing, importing, or deleting a private
library entry never publishes or changes a public review, and publishing a
review never changes the library. Private backup files retain their existing
format and do not include public reviews.

## Publication and privacy

- One review per account and catalog game, with 1–2,000 characters and a rating
  in half-star steps. Ratings retain the existing integer half-star units.
- Publishing requires a verified, normal account session, completed profile,
  reserved username, and public profile. Anonymous and recovery sessions cannot
  publish, edit, delete, or report reviews.
- Only the signed-in author can change or delete their review. Submitted owner
  identifiers are ignored; every mutation binds ownership on the server.
- Setting a profile to private hides its reviews and removes them from community
  averages. Making that profile public restores otherwise visible reviews.
- Spoilers remain behind a closed native disclosure. Long reviews also collapse.
  Text is escaped and never interpreted as HTML. Native controls work without JS.
- Catalog reads never create reviews. Publication checks that the catalog game
  exists before writing. Every form requires CSRF validation; responses are
  private and non-cacheable.

## Reports and moderation

Signed-in players can report another author's visible review for spam, abuse,
unmarked spoilers, or another reason. Reports are deduplicated per reporter and
review. Reporting immediately hides the review for that reader, including their
displayed count and average. It does not automatically remove content for other
readers or claim that an automated content classifier has approved it.

Public review writes and reports share a persistent limit of 30 changes per
account per hour, serialized in PostgreSQL. An author can always remove their
own review, including after reaching this limit or making their profile private.

Server operators can inspect reports without granting the cosmetic Creator badge
any additional authority:

```powershell
flask --app app review-reports
flask --app app moderate-review --review-id 123
flask --app app moderate-review --review-id 123 --hide --apply
flask --app app moderate-review --review-id 123 --restore --apply
```

The moderation command defaults to inspection only. Hiding excludes a review
from public pages and averages; editing that record cannot reset the decision.
Reporters' identifiers and reasons are never projected into public HTML.

## Deployment

Apply migration `012_public_game_reviews.sql` with the normal `migrate-db`
workflow before deploying this code to each PostgreSQL environment. It adds
review, report, and rate-budget tables with constraints, indexes, foreign keys,
row-level security, and no public grants. It does not migrate private notes or
publish existing content. SQLite offline mode keeps its existing private-library
experience and does not expose account-based reviews.
