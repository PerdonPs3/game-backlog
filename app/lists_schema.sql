CREATE TABLE IF NOT EXISTS game_lists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    name_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS game_list_members (
    list_id INTEGER NOT NULL REFERENCES game_lists(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    PRIMARY KEY (list_id, game_id)
);
CREATE INDEX IF NOT EXISTS list_members_by_game ON game_list_members(game_id);
