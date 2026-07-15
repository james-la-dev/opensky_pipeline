CREATE TABLE IF NOT EXISTS polls (
    id            INTEGER PRIMARY KEY,
    requested_at  TEXT NOT NULL,
    api_time      INTEGER,
    state_count   INTEGER NOT NULL,
    http_status   INTEGER
);

CREATE TABLE IF NOT EXISTS observations (
    id              INTEGER PRIMARY KEY,
    poll_id         INTEGER NOT NULL REFERENCES polls(id),
    icao24          TEXT NOT NULL,
    callsign        TEXT,
    origin_country  TEXT,
    time_position   INTEGER,
    last_contact    INTEGER,
    longitude       REAL,
    latitude        REAL,
    baro_altitude   REAL,
    geo_altitude    REAL,
    on_ground       INTEGER NOT NULL,
    velocity        REAL,
    true_track      REAL,
    vertical_rate   REAL,
    squawk          TEXT,
    is_fresh        INTEGER NOT NULL,
    anomaly_flags   TEXT
);

CREATE INDEX IF NOT EXISTS idx_obs_icao_time ON observations(icao24, last_contact);
CREATE INDEX IF NOT EXISTS idx_obs_position  ON observations(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_obs_poll       ON observations(poll_id);
