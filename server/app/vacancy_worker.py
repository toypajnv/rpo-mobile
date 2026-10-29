"""Hourly HeadHunter vacancy refresh worker (no RPO records are modified)."""
from __future__ import annotations

import logging
import os
import time

from .vacancies import scan_once

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vacancies-worker")


def main() -> None:
    interval = max(3600, int(os.getenv("VACANCY_SCAN_INTERVAL_SECONDS", "3600")))
    log.info("Vacancy monitor started, scan interval %s seconds", interval)
    while True:
        started = time.monotonic()
        status, count, message = scan_once()
        if status == "ok":
            log.info("Vacancy scan completed: %d matching offers", count)
        else:
            log.error("Vacancy scan failed: %s", message)
        time.sleep(max(30, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
