"""
Turns a raw `/states/all` response into cleaned dicts
"""

MAX_ALTITUDE, MIN_ALTITUDE = 300.0, 15000.0
FIELD_INDEX = {
    "icao24": 0,
    "callsign": 1,
    "origin_country": 2,
    "time_position": 3,
    "last_contact": 4,
    "longitude": 5,
    "latitude": 6,
    "baro_altitude": 7,
    "on_ground": 8,
    "velocity": 9,
    "true_track": 10,
    "vertical_rate": 11,
    # index 12 is "sensors"
    "geo_altitude": 13,  
    "squawk": 14,
}


def clean_states(raw, previous_positions):
    """
    raw: the response from OpenSky
    previous_positions: {icao24: time_position} from store.latest_time_position()

    Returns list[dict], one per aircraft
    """

    states = raw.get("states") or []
    observations = []
    for state in states:
        row = _parse_state(state)
        row["is_fresh"] = _freshness(row, previous_positions)
        row["anomaly_flags"] = _anomalies(row)
        observations.append(row)
    return observations


def _parse_state(state):
    """Map the array into an object"""

    def at(name):
        i = FIELD_INDEX[name]
        return state[i] if i < len(state) else None

    callsign = at("callsign")
    callsign = callsign.strip() if isinstance(callsign, str) else None
    callsign = callsign or None

    return {
        "icao24": at("icao24"),
        "callsign": callsign,
        "origin_country": at("origin_country"),
        "time_position": _as_int(at("time_position")),
        "last_contact": _as_int(at("last_contact")),
        "longitude": _as_float(at("longitude")),
        "latitude": _as_float(at("latitude")),
        "baro_altitude": _as_float(at("baro_altitude")),
        "geo_altitude": _as_float(at("geo_altitude")),
        "on_ground": 1 if at("on_ground") else 0,
        "velocity": _as_float(at("velocity")),
        "true_track": _as_float(at("true_track")),
        "vertical_rate": _as_float(at("vertical_rate")),
        "squawk": at("squawk"),
    }

def _freshness(row, previous_positions):
    """
    1. If this row looks like a genuinely new position, return it, otherwise return 0

    2. No time_position means nothing to judge, so not fresh. An aircraft we have never seen
    (with a valid time_position) is new. Otherwise fresh only if this reading is newer than the newest we 
    already have. This is what will allow analyze.py tell a live track from OpenSkly repeating a stale
    state.
    """
    t = row["time_position"]
    if t is None:
        return 0
    prev = previous_positions.get(row["icao24"])
    if prev is None:
        return 1
    return 1 if t > prev else 0

def _anomalies(row):
    """
        Attaches a comma-joined series of flags (or None) to indicate when there is an "anomaly" in the data.
    """
    flags = []
    if row["longitude"] is None or row["latitude"] is None:
        flags.append("no_position")
    if row["callsign"] is None:
        flags.append("no_callsign")
    alt = row["baro_altitude"]
    if alt is not None and not (MIN_ALTITUDE <= alt <=MAX_ALTITUDE):
        flags.append("impossible_altitude")
    if row["velocity"] is not None and row["velocity"] < 0:
        flags.append("negative_velocity")
    return ",".join(flags) if flags else None

def _as_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def _as_int(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
