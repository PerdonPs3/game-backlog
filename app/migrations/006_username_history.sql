ALTER TABLE profiles ADD COLUMN username_changed_at BIGINT CHECK (username_changed_at >= 0);
CREATE TABLE profile_usernames (
    username TEXT PRIMARY KEY CHECK (username ~ '^[a-z][a-z0-9_]{2,23}$'),
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    UNIQUE (username, owner_id)
);
INSERT INTO profile_usernames (username, owner_id) SELECT username, id FROM profiles WHERE username IS NOT NULL;
ALTER TABLE profiles ADD CONSTRAINT profile_username_owner FOREIGN KEY (username, id) REFERENCES profile_usernames(username, owner_id);
ALTER TABLE profile_usernames ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON profile_usernames FROM PUBLIC;
