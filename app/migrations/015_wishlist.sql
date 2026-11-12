ALTER TABLE profiles ADD COLUMN share_wishlist BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE wishlist_games (
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    catalog_id BIGINT NOT NULL CHECK (catalog_id > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 200),
    cover_image_id TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    PRIMARY KEY (owner_id, catalog_id)
);
CREATE INDEX wishlist_owner_recent ON wishlist_games(owner_id, created_at DESC, catalog_id DESC);
ALTER TABLE wishlist_games ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON wishlist_games FROM PUBLIC;
