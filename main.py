# main
import logging
import sys
import time
from datetime import datetime, timezone

import requests

from fetch import ApiHandler
from clean import Cleaner
from store import DB_Handler
from analyze import Analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


class Main:
    def __init__(self, polls=10, intervals=15, db_path="flights.db"):
        """
        polls = amount of polls before analysing
        intervals = intervals between polls in seconds
        """
        self.polls = polls
        self.intervals = intervals
        self.db_path = db_path

        self.api_handler = ApiHandler()
        self.db_handler = DB_Handler(self.db_path)
        self.cleaner = Cleaner()
        self.analyzer = Analyzer(self.db_handler)

    def run_poll(self):
        """
        Fetch, clean, store.
        """
        requested_at = datetime.now(timezone.utc).isoformat()
        try:
            raw = self.api_handler.get_states()
        except requests.HTTPError as err:
            # store logs (including failed polls)
            status = err.response.status_code if err.response is not None else None
            self.db_handler.write_poll(
                {
                    "requested_at": requested_at,
                    "api_time": None,
                    "state_count": 0,
                    "http_status": status,
                },
                [],
            )
            raise

        previous = (
            self.db_handler.latest_time_position()
        )  # snapshot BEFORE this poll is written
        observations = self.cleaner.clean_states(raw, previous)

        poll_meta = {
            "requested_at": requested_at,
            "api_time": raw.get("time"),
            "state_count": len(raw.get("states") or []),
            "http_status": 200,
        }
        _, count = self.db_handler.write_poll(poll_meta, observations)
        return count

    def main(self):
        completed = 0
        try:
            for i in range(self.polls):
                try:
                    written = self.run_poll()
                    completed += 1
                    log.info(
                        "poll %d/%d: wrote %d aircraft", i + 1, self.polls, written
                    )
                except Exception:
                    log.exception("poll %d/%d failed, continuing", i + 1, self.polls)

                if i < self.polls - 1:
                    time.sleep(self.intervals)

            if completed == 0:
                log.error("no polls succeeded, skipping analyses")
                sys.exit(1)

            log.info("polling done (%d successful), running analysis...", completed)
            self.analyzer.run_analysis()

        finally:
            self.db_handler.close()


if __name__ == "__main__":
    main = Main()
    main.main()
