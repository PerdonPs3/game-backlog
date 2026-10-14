CREATE TABLE IF NOT EXISTS games (
    id INTEGER,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    platform TEXT NOT NULL CHECK (length(trim(platform)) > 0),
    status TEXT NOT NULL DEFAULT 'Backlog'
        CHECK (status IN ('Backlog', 'Playing', 'Completed')),
    rating INTEGER CHECK (rating BETWEEN 1 AND 10),
    review TEXT NOT NULL DEFAULT '',
    igdb_id INTEGER,
    cover_image_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
);
