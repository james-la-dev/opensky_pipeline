# SQLite writes, schema definition

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

OBSERVATION_COLUMNS = (
    "poll_id",
    "icao24",
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude",
    "geo_altitude",
    "on_ground",
    "velocity",
    "true_track",
    "vertical_rate",
    "squawk",
    "is_fresh",
    "anomaly_flags",
)


class Store:
    def __init__(self, db_path="flights.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        self._create_schema()

    def _create_schema(self):
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        self.conn.close()

    def write_poll(self, poll_meta, observations):
        """
        Writes one poll and its observations as a single unit

        `with self.conn` commits on success and rolls back on any exception, so a partial failure cannot leave
        a poll row claiming more aircraft than were actually stored.
        """
        with self.conn:
            poll_id = self._record_poll(**poll_meta)
            for obs in observations:
                obs["poll_id"] = poll_id

            count = self._insert_observations(observations)
        return poll_id, count

    def _record_poll(self, requested_at, api_time, state_count, http_status):
        """
        Insert a poll row and return its id

        Written even for failed polls (non-200, zero-states). Without these rows, a gap in the data is
        indistinguishable from an hour in which no aircraft were airborne.
        """
        cur = self.conn.execute(
            """
            INSERT INTO polls (requested_at, api_time, state_count, http_status)
            VALUES (:request_at, :api_time, :state_count, :http_status)
            """,
            {
                "requested_at": requested_at,
                "api_time": api_time,
                "state_count": state_count,
                "http_status": http_status,
            },
        )
        return cur.lastrowid

    def _insert_observations(self, observations):
        """
        Bulk-insert cleaned observation dicts

        Columns are named rather than positional, so adding a column later is a deliberate schema change and
        not a silent column-order bug.
        """
        if not observations:
            return 0

        columns = ", ".join(OBSERVATION_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in OBSERVATION_COLUMNS)
        sql = f"INSERT INTO observations ({columns}) VALUES ({placeholders})"

        self.conn.executemany(sql, observations)
        return len(observations)

    def latest_time_position(self):
        """
        Most recent time_position per aircraft, as {icao24: time_position}.

        clean.py compares each incoming state vector against this to decide whether OpenSky handed us a
        genuinely new reading or repeated a stale one. Must be called BEFORE the current poll is written,
        or every aaircraft compares against itself and is_fresh is always 0.
        """

        rows = self.conn.execute(
            """
            SELECT icao24, MAX(time_position) AS latest
            FROM observations
            WHERE time_position IS NOT NULL
            GROUP BY icao24
            """
        ).fetchall()
        return {row["icao24"]: row["latest"] for row in rows}

    def query(self, sql, params=()):
        """
        Simply runs a readonly query, returns Rows.
        """
        return self.conn.execute(sql, params).fetchall()
