# aggregate queries, simple stats/anomaly checks


class Analyzer:
    def __init__(self, db_handler, stale_threshold=2):
        self.db_handler = db_handler
        self.stale_threshold = stale_threshold

    def run_analysis(self):
        """
        Compute every section, print the report, and return the raw results.
        """

        results = {
            "run": self._run_summary(),
            "traffic": self._traffic(),
            "altitude": self._altitude_distribution(),
            "tracking_loss": self._tracking_loss(),
            "quality": self._data_quality(),
        }
        print(self._render(results))
        return results

    def _run_summary(self):
        row = self.db_handler.query(
            """
            SELECT COUNT(*) AS total,
                SUM(CASE WHEN http_status = 200 THEN 1 ELSE 0 END) AS ok,
                MIN(requested_at) AS started,
                MAX(requested_at) AS ended
            FROM polls
            """
        )[0]
        return {
            "total_polls": row["total"] or 0,
            "ok_polls": row["ok"] or 0,
            "started": row["started"],
            "ended": row["ended"],
        }

    def _traffic(self):
        """
        Finds the traffic within the given airspace
        """
        totals = self.db_handler.query(
            "SELECT COUNT(DISTINCT icao24) AS aircraft, COUNT(*) AS obs FROM observations"
        )[0]
        per_poll = self.db_handler.query(
            "SELECT poll_id, COUNT(*) AS n FROM observations GROUP by poll_id"
        )
        counts = [r["n"] for r in per_poll]
        split = self.db_handler.query(
            """
                SELECT SUM(CASE WHEN on_ground = 1 THEN 1 ELSE 0 END) AS on_ground,
                    SUM(CASE WHEN on_ground = 0 THEN 1 ELSE 0 END) AS airborne
                FROM observations
                """
        )[0]
        return {
            "distinct_aircraft": totals["aircraft"] or 0,
            "observations": totals["obs"] or 0,
            "mean_per_poll": round(sum(counts) / len(counts), 1) if counts else 0,
            "peak_per_poll": max(counts) if counts else 0,
            "on_ground": split["on_ground"] or 0,
            "airborne": split["airborne"] or 0,
        }

    def _altitude_distribution(self):
        """ """
        rows = self.db_handler.query(
            """
            SELECT CASE
                    WHEN baro_altitude < 1000 THEN '0-1km'
                    WHEN baro_altitude < 3000 THEN '1-3km'
                    WHEN baro_altitude < 6000 THEN '3-6km'
                    WHEN baro_altitude < 9000 THEN '9-12km'
                    ELSE '12km+'
                END AS band,
                COUNT(*) as n
            FROM observations
            WHERE on_ground = 0 AND baro_altitude IS NOT NULL
            GROUP BY band
            ORDER BY MIN(baro_altitude)
            """
        )
        return [(r["band"], r["n"]) for r in rows]

    def _tracking_loss(self):
        """
        Finds any "lost aircrafts" by getting the last poll we saw it ("last_seen"), and the last
        poll where it had a "genuinely" new position ("last_fresh").
        """
        rows = self.db_handler.query(
            """
            SELECT icao24,
                MAX(poll_id) AS last_seen,
                MAX(CASE WHEN is_fresh = 1 THEN poll_id END) AS last_fresh
            FROM observations
            GROUP BY icao24
            """
        )
        frozen = []
        never_fresh = 0
        for r in rows:
            if r["last_fresh"] is None:
                never_fresh += 1
                continue
            stale_tail = r["last_seen"] - r["last_fresh"]
            if stale_tail >= self.stale_threshold:
                frozen.append((r["icao24"], stale_tail))

        frozen.sort(key=lambda pair: pair[1], reverse=True)
        return {"frozen": frozen, "never_fresh": never_fresh}

    def _data_quality(self):
        total = self.db_handler.query(
            "SELECT COUNT(*) AS n FROM observations WHERE anomaly_flags IS NOT NULL"
        )[0]["n"]
        breakdown = self.db_handler.query(
            """
            SELECT anomaly_flags, COUNT(*) AS n
            FROM observations
            WHERE anomaly_flags IS NOT NULL
            GROUP BY anomaly_flags
            ORDER BY n DESC
            """
        )
        return {
            "flagged": total or 0,
            "breakdown": [(r["anomaly_flags"], r["n"]) for r in breakdown],
        }

    def _render(self, r):
        bar_width = 20
        run, t = r["run"], r["traffic"]
        line = "=" * 60
        out = [line, "OpenSky NZ airspace analysis", line]
        out.append(f"Run: {run['ok_polls']}/{run['total_polls']} polls ok"
                   f"\t({run['started']} -> {run['ended']})")

        out.append("Traffic:")
        out.append(f"\tdistinct aircrafts: {t['distinct_aircraft']}")
        out.append(f"\tobservations: {t['observations']}")
        out.append(f"\tmean aircraft/poll: {t['mean_per_poll']}")
        out.append(f"\tpeak: {t['peak_per_poll']}")
        out.append(f"\tairborne: {t['airborne']}")
        out.append(f"\ton ground: {t['on_ground']}")

        out.append("")
        out.append("Altitude distribution (airborne readings)")
        alt = r["altitude"]
        peak = max((n for _, n in alt), default=0)
        for band, n in alt:
            bar = "#" * round(bar_width * n / peak) if peak else ""
            out.append(f"\t{band:<7}{n:>6}  {bar}")
 
        out.append("")
        loss = r["tracking_loss"]
        out.append(f"Tracking loss (position frozen >= {self.stale_threshold} polls while still listed)")
        if loss["frozen"]:
            out.append(f"\t\t{len(loss['frozen'])} aircraft")
            for icao, tail in loss["frozen"][:10]:
                out.append(f"\t\t{icao}  frozen | {tail} polls")
        else:
            out.append("\tnone")
        if loss["never_fresh"]:
            out.append(f"\t({loss['never_fresh']} more never reported a moving position)")
 
        out.append("")
        q = r["quality"]
        out.append(f"Data quality: {q['flagged']} observations flagged")
        for flags, n in q["breakdown"][:5]:
            out.append(f"\t\t{flags}: {n}")
 
        out.append(line)
        return "\n".join(out)

