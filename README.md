# OpenSky NZ Airspace Pipeline
A small data pipeline that polls the OpenSky Network live aircraft API for the airspace over New Zealand, cleans the raw state vectors, sotres them in SQLite, and prints a short analysis of the collected window. 

It runs a single Python process. Fetch, clean, store, and analyse are seperate modules coordinated by `main.py`. 

## What it does
Each polls asks OpenSky for every aircraft currently inside a bounding box around New Zealand. A poll returns a scnapshot (not a stream), so the pipeline takes several snapshots a fixed interval apart and then reasons about what changed between them. 

Each poll runs three steps. 
1. Fetches `/states/all` for the NZ bounding box, refreshing the OAuth2 token when it has expired. 
2. Parses each state vector, coerces types, normalises empty callsigns to `null`, and attaches two derived fields. One is whether the reading is a genuinely new position (`is_fresh`), the other is a comma-seperated list of anomaly flags.
3. Writes the poll and all of its observations to SQLite as one transaction, so a poll row can never claim more aircrafts that what were actually stored.

After the configured number of polls, it runs the analysis and prints a plain-text report covering traffic volume, altitude distribution, tracking loss, and data quality.

Failled polls (a non-200 response or a network error) are still recorded as poll rows with zero observations. Without them, a gap caused by an API outage would look identical to a quiet hour with no aircraft airborne. 

## Data Model
`polls` records one row per attempt, successful or not, with the request timestamp, the API's own timestamp, the number of states returned and the HTTP status.
  
`observations` records one row per aircraft per poll, linked back to its poll by `poll_id`. Storing every reading rather than only the latest position is what makes the between-poll analysis possible. Freshness and tracking loss both depend on comparing an aircraft against its own earlier readings.  
  
Three indexes support the analysis queries. `(icao24, last_contact)` covers per-aircraft history, `(latitude, longitude)` covers position lookups, and `poll_id` covers the per-poll aggregates. 

## Derived fields
`is_fresh` marks whether a reading is a new position or Opensky repeating a stale one. A snapshot API will hand back the same `time_position` for an aircraft that has not sent a new update, so the same coordinates can appear across several polls. before each poll is written, the pipleine reads the newest `time_position` it already holds for each aircraft and compares. A reading is fresh if the aircraft is new to the dataset, or if its `time_position` is newer than anything already sorted. This is the distinction that lets the analyser seperate a live track from a frozen one.

`anomaly_flags` is a comma-seperated string, or `null` when the row is clean. There are four flags at the moment:
* `no_position`: when latitude or longitude is missing
* `no_callsign`: when the callsign is missing or blank
* `impossible_altitude`: When the altitude falls outside 300m to 15 km
* `negative_velocity`: when the reported speed is below zero

The flags are recorded rather than dropped, so that the report can show how much of the feed is imperfect.

## The analysis
The printed report has four sections:
* **Traffic**: Distinct aircraft, total observations, mean and peak aircraft per poll, and an airborne versus on-ground split.
* **Altitude distribution**: A graph of airborne readings across altitude bands.
* **Tracking loss**: Aircraft still appearing in the feed whose position has not changed for at least a set number of polls (the `stale_threshold`, default 2), plus a count of aurcraft that never reported a moving position at all. This is where `is_fresh` pays off.
* **Data quality**: How many observations carried anomaly flags and the breakdown by flag combination.

## Design notes
### SQLite
The data is fixed-shape and relational, a set of polls with observations belonging to each one. That is a natural fit for a single table with a foreign key, and SQLite handles it without a server to run or a schema migration tool to manage. Postgres or Mongo would add operational weight the problem does not call for.

### Why one process
This pipline simply fetches, stores, and analyses over a short window of data. Splitting that into services or adding a queue would be degrade the effort spent on the actual problem.

### Polling
OpenSky's API is request-response, not a stream. There is no websocket to connect to, so the pipeline works by taking snapshots and comparing them. 


