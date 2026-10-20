CREATE TABLE profiles (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '' CHECK (length(display_name) <= 60),
    bio TEXT NOT NULL DEFAULT '' CHECK (length(bio) <= 500),
    avatar TEXT NOT NULL DEFAULT 'controller' CHECK (avatar IN ('controller', 'star', 'ghost', 'rocket')),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
ALTER TABLE games ADD COLUMN owner_id UUID REFERENCES profiles(id);
ALTER TABLE game_lists ADD COLUMN owner_id UUID REFERENCES profiles(id);
ALTER TABLE games ADD CONSTRAINT games_id_owner_unique UNIQUE (id, owner_id);
ALTER TABLE game_lists ADD CONSTRAINT game_lists_id_owner_unique UNIQUE (id, owner_id);
ALTER TABLE game_lists DROP CONSTRAINT game_lists_name_key_key;
ALTER TABLE game_lists ADD CONSTRAINT game_lists_owner_name_unique UNIQUE NULLS NOT DISTINCT (owner_id, name_key);
ALTER TABLE game_list_members ADD COLUMN owner_id UUID REFERENCES profiles(id);
ALTER TABLE game_list_members ADD CONSTRAINT members_game_owner FOREIGN KEY (game_id, owner_id) REFERENCES games(id, owner_id) ON DELETE CASCADE;
ALTER TABLE game_list_members ADD CONSTRAINT members_list_owner FOREIGN KEY (list_id, owner_id) REFERENCES game_lists(id, owner_id) ON DELETE CASCADE;
CREATE INDEX games_owner_created ON games(owner_id, created_at);
CREATE INDEX lists_owner ON game_lists(owner_id);
CREATE TABLE account_sessions (
    id_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES profiles(id),
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    valid_until BIGINT NOT NULL,
    recovery SMALLINT NOT NULL DEFAULT 0 CHECK (recovery IN (0, 1))
);
CREATE INDEX account_sessions_expiration ON account_sessions(valid_until);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON profiles, account_sessions FROM PUBLIC;
