CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'queued',
    sleep_seconds INTEGER NOT NULL DEFAULT 3,
    message TEXT,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jobs_status ON jobs (status) WHERE status = 'queued';

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS job_type TEXT NOT NULL DEFAULT 'sleep',
    ADD COLUMN IF NOT EXISTS payload JSONB;

CREATE TABLE IF NOT EXISTS spotify_tracks (
    id                   SERIAL PRIMARY KEY,
    track_name           TEXT NOT NULL,
    artists              TEXT NOT NULL,
    artist_count         INTEGER,
    released_year        INTEGER,
    released_month       INTEGER,
    released_day         INTEGER,
    streams              BIGINT,
    in_spotify_playlists INTEGER,
    in_spotify_charts    INTEGER,
    in_apple_playlists   INTEGER,
    in_apple_charts      INTEGER,
    in_deezer_playlists  INTEGER,
    in_deezer_charts     INTEGER,
    in_shazam_charts     INTEGER,
    bpm                  INTEGER,
    key                  TEXT,
    mode                 TEXT,
    danceability         SMALLINT,
    valence              SMALLINT,
    energy               SMALLINT,
    acousticness         SMALLINT,
    instrumentalness     SMALLINT,
    liveness             SMALLINT,
    speechiness          SMALLINT,
    ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_spotify_tracks_name
    ON spotify_tracks (lower(track_name));
