ALTER TABLE profiles ADD COLUMN background_key TEXT NOT NULL DEFAULT 'castle' CHECK (background_key IN ('castle', 'aurora', 'obsidian', 'custom'));
ALTER TABLE profiles ADD COLUMN background_image BYTEA CHECK (octet_length(background_image) <= 2097152);
ALTER TABLE profiles ADD COLUMN share_background BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE profiles ADD COLUMN share_badges BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE profiles ADD COLUMN featured_badges TEXT NOT NULL DEFAULT '' CHECK (length(featured_badges) <= 256);
CREATE TABLE profile_achievements (
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    badge_key TEXT NOT NULL CHECK (badge_key IN ('newcomer', 'collector', 'archivist', 'curator', 'legend', 'finisher', 'completionist', 'reviewer', 'critic')),
    earned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    acknowledged_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (owner_id, badge_key)
);
ALTER TABLE profile_achievements ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON profile_achievements FROM PUBLIC;
