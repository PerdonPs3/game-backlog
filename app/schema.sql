CREATE TABLE IF NOT EXISTS games (
    id INTEGER,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    platform TEXT NOT NULL CHECK (length(trim(platform)) > 0),
    status TEXT NOT NULL DEFAULT 'Backlog'
        CHECK (status IN ('Backlog', 'Playing', 'Completed', 'On hold', 'Dropped')),
    rating INTEGER CHECK (rating BETWEEN 1 AND 10),
    review TEXT NOT NULL DEFAULT '',
    igdb_id INTEGER,
    cover_image_id TEXT,
    started_on TEXT,
    completed_on TEXT,
    is_favorite INTEGER NOT NULL DEFAULT 0 CHECK (is_favorite IN (0, 1)),
    is_goty INTEGER NOT NULL DEFAULT 0 CHECK (is_goty IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    CHECK (started_on IS NULL OR completed_on IS NULL OR completed_on >= started_on)
);
