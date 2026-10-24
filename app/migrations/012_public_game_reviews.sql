CREATE TABLE public_game_reviews (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    catalog_id BIGINT NOT NULL CHECK (catalog_id > 0),
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 10),
    body TEXT NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 2000),
    has_spoilers BOOLEAN NOT NULL DEFAULT FALSE,
    moderation_hidden BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    UNIQUE (catalog_id, owner_id)
);
CREATE INDEX public_reviews_catalog ON public_game_reviews(catalog_id, updated_at DESC, id DESC);
CREATE TABLE public_review_reports (
    review_id BIGINT NOT NULL REFERENCES public_game_reviews(id) ON DELETE CASCADE,
    reporter_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    reason TEXT NOT NULL CHECK (reason IN ('spam', 'abuse', 'spoilers', 'other')),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    PRIMARY KEY (review_id, reporter_id)
);
CREATE TABLE public_review_events (
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE INDEX public_review_events_owner ON public_review_events(owner_id, created_at);
ALTER TABLE public_game_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_review_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_review_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public_game_reviews, public_review_reports, public_review_events FROM PUBLIC;
