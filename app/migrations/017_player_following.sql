ALTER TABLE profiles ADD COLUMN share_connections BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE player_follows (
    follower_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    followed_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('pending', 'accepted')),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    PRIMARY KEY (follower_id, followed_id),
    CHECK (follower_id <> followed_id)
);
CREATE INDEX player_follows_incoming ON player_follows(followed_id, state, created_at);

CREATE TABLE player_blocks (
    blocker_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    blocked_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id <> blocked_id)
);
CREATE INDEX player_blocks_incoming ON player_blocks(blocked_id, blocker_id);

CREATE TABLE player_follow_events (
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE INDEX player_follow_events_owner ON player_follow_events(owner_id, created_at);
ALTER TABLE player_follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_follow_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON player_follows, player_blocks, player_follow_events FROM PUBLIC;
