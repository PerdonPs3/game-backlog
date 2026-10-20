CREATE TABLE profile_showcase (
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5),
    game_id BIGINT NOT NULL,
    PRIMARY KEY (owner_id, position),
    UNIQUE (owner_id, game_id),
    FOREIGN KEY (game_id, owner_id) REFERENCES games(id, owner_id) ON DELETE CASCADE
);
ALTER TABLE profile_showcase ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON profile_showcase FROM PUBLIC;
