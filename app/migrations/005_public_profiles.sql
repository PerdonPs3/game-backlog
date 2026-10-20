ALTER TABLE profiles ADD COLUMN username TEXT UNIQUE CHECK (username ~ '^[a-z][a-z0-9_]{2,23}$');
ALTER TABLE profiles ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE profiles ADD COLUMN share_bio BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE profiles ADD COLUMN share_showcase BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE profiles ADD CONSTRAINT public_profile_identity CHECK (NOT is_public OR (username IS NOT NULL AND length(trim(display_name)) > 0));
