"""Hourly vacancy refresh plus manual immediate-scan requests from the web UI."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .database import SessionLocal
from .vacancies import VacancyRefreshRequest, init_tables, scan_once

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vacancies-worker")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def claim_refresh() -> int | None:
    """The deployment has exactly one vacancies-worker process."""
    init_tables()
    with SessionLocal() as db:
        pending = db.scalar(
            select(VacancyRefreshRequest)
            .where(VacancyRefreshRequest.state == "queued")
            .order_by(VacancyRefreshRequest.id.asc())
            .limit(1)
        )
        if pending is None:
            return None
        pending.state = "running"
        pending.started_at = now_utc()
        db.commit()
        return pending.id


def finish_refresh(request_id: int, status: str, error: str) -> None:
    with SessionLocal() as db:
        pending = db.get(VacancyRefreshRequest, request_id)
        if pending:
            pending.state = "done" if status == "ok" else "partial" if status == "partial" else "error"
            pending.finished_at = now_utc()
            pending.error = error[:1400]
            db.commit()


def perform_scan(request_id: int | None = None) -> None:
    try:
        status, count, message = scan_once()
        if status == "ok":
            log.info("Vacancy scan completed: %d jobs", count)
        else:
            log.warning("Vacancy scan status=%s count=%d: %s", status, count, message)
    except Exception as exc:
        status, message = "error", str(exc)
        log.exception("Vacancy scan crashed; the worker continues")
    if request_id is not None:
        finish_refresh(request_id, status, message)


def main() -> None:
    interval = max(3600, int(os.getenv("VACANCY_SCAN_INTERVAL_SECONDS", "3600")))
    log.info("Vacancy monitor started, hourly interval=%d seconds", interval)
    perform_scan()
    next_hourly = time.monotonic() + interval
    while True:
        request_id = claim_refresh()
        if request_id is not None:
            perform_scan(request_id)
            # A manual scan counts as a recent scan; don't start a second scan
            # immediately after it unless another explicit request is queued.
            next_hourly = time.monotonic() + interval
        elif time.monotonic() >= next_hourly:
            perform_scan()
            next_hourly = time.monotonic() + interval
        else:
            time.sleep(5)


if __name__ == "__main__":
    main()
