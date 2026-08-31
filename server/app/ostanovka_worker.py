from __future__ import annotations

import argparse
import email
from email.header import decode_header, make_header
import imaplib
import logging
import os
from pathlib import Path
import tempfile
import time

from .database import Base, SessionLocal, engine
from .stop_registry import import_registry

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ostanovka-mail")


def decoded(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def import_file(path: str | Path, *, file_name: str = "", message_id: str = "", sender: str = ""):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        return import_registry(db, path, file_name=file_name, message_id=message_id, sender=sender)


def process_message(raw_message: bytes) -> bool:
    message = email.message_from_bytes(raw_message)
    message_id = decoded(message.get("Message-ID"))
    sender = decoded(message.get("From"))
    processed = False
    for part in message.walk():
        filename = decoded(part.get_filename())
        if not filename or not filename.lower().endswith(".xlsb"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        with tempfile.NamedTemporaryFile(prefix="stop-registry-", suffix=".xlsb", delete=False) as temp:
            temp.write(payload)
            temp_path = temp.name
        try:
            result = import_file(temp_path, file_name=filename, message_id=message_id, sender=sender)
            log.info("registry imported duplicate=%s source_rows=%s indexed_rows=%s unique_passes=%s file=%s", result.duplicate, result.source_rows, result.indexed_rows, result.unique_passes, filename)
            processed = True
        finally:
            Path(temp_path).unlink(missing_ok=True)
    return processed


def poll_once() -> int:
    host = os.getenv("STOP_IMAP_HOST", "").strip()
    username = os.getenv("STOP_IMAP_USERNAME", "").strip()
    password = os.getenv("STOP_IMAP_PASSWORD", "")
    if not host or not username or not password:
        log.warning("IMAP is not configured: STOP_IMAP_HOST/USERNAME/PASSWORD are required")
        return 0

    port = int(os.getenv("STOP_IMAP_PORT", "993"))
    folder = os.getenv("STOP_IMAP_FOLDER", "INBOX")
    sender_filter = os.getenv("STOP_IMAP_SENDER", "").strip()
    subject_filter = os.getenv("STOP_IMAP_SUBJECT", "").strip()

    with imaplib.IMAP4_SSL(host, port) as client:
        client.login(username, password)
        status, _ = client.select(folder)
        if status != "OK":
            raise RuntimeError(f"Cannot select IMAP folder {folder}")
        criteria = ["UNSEEN"]
        if sender_filter:
            criteria += ["FROM", f'"{sender_filter}"']
        if subject_filter:
            criteria += ["SUBJECT", f'"{subject_filter}"']
        status, data = client.uid("search", None, *criteria)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        uids = [uid for uid in (data[0] or b"").split() if uid]
        processed_count = 0
        for uid in uids:
            status, fetched = client.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not fetched:
                continue
            raw_message = next((item[1] for item in fetched if isinstance(item, tuple) and len(item) > 1), None)
            if not raw_message:
                continue
            try:
                if process_message(raw_message):
                    client.uid("store", uid, "+FLAGS", "(\\Seen)")
                    processed_count += 1
            except Exception:
                log.exception("failed to process IMAP message uid=%s", uid.decode(errors="ignore"))
        return processed_count


def run_forever() -> None:
    interval = max(60, int(os.getenv("STOP_IMAP_POLL_SECONDS", "60")))
    while True:
        try:
            count = poll_once()
            if count:
                log.info("processed %s registry message(s)", count)
        except Exception:
            log.exception("IMAP polling error")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import stop registry from XLSB or poll an IMAP mailbox")
    parser.add_argument("--file", help="Import one local XLSB file and exit")
    args = parser.parse_args()
    if args.file:
        print(import_file(args.file))
        return
    run_forever()


if __name__ == "__main__":
    main()
