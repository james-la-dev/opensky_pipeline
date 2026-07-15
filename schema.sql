-- One row per API request, written whether or not the request succeeded. Records what was asked for (bounding box), when it was asked, what openSky's own clock said, and how many state vectors came back before deduplication. This is the table that lets you distinguish "no aircraft were in the box" from "the poll failed", which is otherwise indistinguishable in the data.
CREATE TABLE polls (
    id            INTEGER PRIMARY KEY,
    requested_at  INTEGER NOT NULL,   
    api_time      INTEGER,            
    bbox_lamin    REAL, 
    bbox_lamax    REAL,
    bbox_lomin    REAL, 
    bbox_lomax    REAL,
    http_status   INTEGER,
    state_count   INTEGER             
);

-- The fact table. One row per distinct state vector, meaning per aircraft per genuine position update, not per poll. OpenSky returns the last known state regardless of age, so consecutive polls frequently return byte-identical readings for the same aircraft. The unique constraint on `(icao24, dedup_key)` is what envorces this where `dedup_key` is the position timestamp falling back to last contact when no position has ever been received. Units are metric trhoughout, matching the API: altitudes in metres, velocity and vertical rate in metres per second, track in degrees.
CREATE TABLE observations (
    id              INTEGER PRIMARY KEY,
    icao24          TEXT NOT NULL REFERENCES aircraft(icao24),
    callsign        TEXT,               
    time_position   INTEGER,           
    last_contact    INTEGER NOT NULL,
    longitude       REAL,
    latitude        REAL,
    baro_altitude   REAL,               
    geo_altitude    REAL,               
    on_ground       INTEGER NOT NULL,   
    velocity        REAL,               
    true_track      REAL,               
    vertical_rate   REAL,               
    squawk          TEXT,               
    spi             INTEGER NOT NULL,
    position_source INTEGER NOT NULL,    
    dedup_key       INTEGER NOT NULL,   
    anomaly_flags   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (icao24, dedup_key)
);

CREATE INDEX idx_obs_icao_time ON observations(icao24, last_contact);
CREATE INDEX idx_obs_position  ON observations(latitude, longitude);
