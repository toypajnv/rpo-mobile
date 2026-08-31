from __future__ import annotations

import argparse
import email
from email.header import decode_header, make_header
from email.utils import parseaddr
import imaplib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .stop_registry import StopRegistryImport, import_registry

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


def _message_imported(message_id: str) -> bool:
    if not message_id:
        return False
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        return bool(db.scalar(select(StopRegistryImport.id).where(StopRegistryImport.message_id == message_id).limit(1)))


def _sender_filter_allows_any(expected: str | None) -> bool:
    return (expected or "").strip() in {"", "*"}


def _allowed_sender(raw_sender: str, expected: str) -> bool:
    if _sender_filter_allows_any(expected):
        return True
    actual = parseaddr(raw_sender or "")[1].strip().lower()
    return bool(actual and actual == expected.strip().lower())


def _allowed_subject(actual: str, expected: str) -> bool:
    return bool(expected and (actual or "").strip().casefold() == expected.strip().casefold())


def _allowed_recipient(recipients: object, expected: str) -> bool:
    if not expected:
        return False
    expected_normalized = expected.strip().lower()
    if not isinstance(recipients, list):
        return False
    return any(str(item).strip().lower() == expected_normalized for item in recipients)


def _save_and_import(payload: bytes, *, filename: str, message_id: str, sender: str) -> bool:
    with tempfile.NamedTemporaryFile(prefix="stop-registry-", suffix=".xlsb", delete=False) as temp:
        temp.write(payload)
        temp_path = temp.name
    try:
        result = import_file(temp_path, file_name=filename, message_id=message_id, sender=sender)
        log.info(
            "registry imported duplicate=%s source_rows=%s indexed_rows=%s unique_passes=%s file=%s",
            result.duplicate,
            result.source_rows,
            result.indexed_rows,
            result.unique_passes,
            filename,
        )
        return True
    finally:
        Path(temp_path).unlink(missing_ok=True)


def process_message(raw_message: bytes, *, expected_subject: str = "", sender_filter: str = "*") -> bool:
    """Validate one raw IMAP message and import its single XLSB attachment."""
    message = email.message_from_bytes(raw_message)
    message_id = decoded(message.get("Message-ID"))
    sender = decoded(message.get("From"))
    subject = decoded(message.get("Subject"))

    # IMAP SUBJECT search is a substring match, so enforce an exact subject after fetch.
    if expected_subject and not _allowed_subject(subject, expected_subject):
        return False
    if not _allowed_sender(sender, sender_filter):
        return False

    attachments: list[tuple[str, bytes]] = []
    for part in message.walk():
        filename = decoded(part.get_filename())
        if not filename or not filename.lower().endswith(".xlsb"):
            continue
        payload = part.get_payload(decode=True)
        if payload:
            attachments.append((filename, payload))

    if not attachments:
        return False
    if len(attachments) != 1:
        raise ValueError("Ожидалось ровно одно вложение .xlsb в письме")

    filename, payload = attachments[0]
    return _save_and_import(payload, filename=filename, message_id=message_id, sender=sender)


def _resend_json(path: str, *, api_key: str, query: dict[str, object] | None = None) -> dict:
    base = os.getenv("STOP_RESEND_API_BASE", "https://api.resend.com").rstrip("/")
    url = f"{base}{path}"
    if query:
        url += "?" + urlencode({key: value for key, value in query.items() if value is not None})
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "RPO-Ostanovka/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend API HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Resend API unavailable: {exc.reason}") from exc


def _download(url: str, *, max_bytes: int) -> bytes:
    request = Request(url, headers={"User-Agent": "RPO-Ostanovka/1.0"}, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise ValueError("Вложение превышает допустимый размер")
            payload = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise RuntimeError(f"Attachment download HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Attachment download failed: {exc.reason}") from exc
    if len(payload) > max_bytes:
        raise ValueError("Вложение превышает допустимый размер")
    return payload


def poll_resend_once() -> int:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender_filter = os.getenv("STOP_RESEND_SENDER", "*").strip() or "*"
    subject_filter = os.getenv("STOP_RESEND_SUBJECT", "").strip()
    recipient_filter = os.getenv("STOP_RESEND_TO", "").strip()
    if not all((api_key, subject_filter, recipient_filter)):
        log.warning(
            "Resend receiving is disabled until RESEND_API_KEY, STOP_RESEND_SUBJECT and STOP_RESEND_TO are configured"
        )
        return 0

    limit = max(1, min(100, int(os.getenv("STOP_RESEND_LIST_LIMIT", "50"))))
    max_bytes = max(1, int(os.getenv("STOP_MAX_ATTACHMENT_MB", "25"))) * 1024 * 1024
    listing = _resend_json("/emails/receiving", api_key=api_key, query={"limit": limit})
    messages = listing.get("data") or []
    if not isinstance(messages, list):
        raise RuntimeError("Unexpected Resend receiving response")

    messages = sorted(messages, key=lambda item: str((item or {}).get("created_at", "")))
    processed_count = 0
    for item in messages:
        if not isinstance(item, dict):
            continue
        sender = str(item.get("from") or "")
        subject = str(item.get("subject") or "")
        recipients = item.get("to")
        if not _allowed_sender(sender, sender_filter):
            continue
        if not _allowed_subject(subject, subject_filter):
            continue
        if not _allowed_recipient(recipients, recipient_filter):
            continue

        email_id = str(item.get("id") or "").strip()
        message_id = str(item.get("message_id") or "").strip() or (f"resend:{email_id}" if email_id else "")
        if not email_id or not message_id or _message_imported(message_id):
            continue

        attachment_meta = item.get("attachments") or []
        xlsb_meta = [
            attachment for attachment in attachment_meta
            if isinstance(attachment, dict) and str(attachment.get("filename") or "").lower().endswith(".xlsb")
        ]
        if not xlsb_meta:
            continue
        if len(xlsb_meta) != 1:
            raise ValueError(f"Письмо {email_id}: ожидалось ровно одно вложение .xlsb")

        attachment_listing = _resend_json(f"/emails/receiving/{email_id}/attachments", api_key=api_key)
        attachments = attachment_listing.get("data") or []
        xlsb = [
            attachment for attachment in attachments
            if isinstance(attachment, dict) and str(attachment.get("filename") or "").lower().endswith(".xlsb")
        ]
        if len(xlsb) != 1:
            raise ValueError(f"Письмо {email_id}: API вернул некорректный набор XLSB-вложений")

        attachment = xlsb[0]
        filename = str(attachment.get("filename") or "registry.xlsb")
        declared_size = int(attachment.get("size") or 0)
        if declared_size and declared_size > max_bytes:
            raise ValueError(f"Письмо {email_id}: XLSB-вложение слишком большое")
        download_url = str(attachment.get("download_url") or "").strip()
        if not download_url:
            raise RuntimeError(f"Письмо {email_id}: Resend не вернул download_url")

        payload = _download(download_url, max_bytes=max_bytes)
        if _save_and_import(payload, filename=filename, message_id=message_id, sender=sender):
            processed_count += 1

    return processed_count


def poll_imap_once() -> int:
    host = os.getenv("STOP_IMAP_HOST", "").strip()
    username = os.getenv("STOP_IMAP_USERNAME", "").strip()
    password = os.getenv("STOP_IMAP_PASSWORD", "")
    sender_filter = os.getenv("STOP_IMAP_SENDER", "*").strip() or "*"
    subject_filter = os.getenv("STOP_IMAP_SUBJECT", "").strip()
    if not all((host, username, password, subject_filter)):
        log.warning(
            "IMAP import is disabled until STOP_IMAP_HOST, STOP_IMAP_USERNAME, STOP_IMAP_PASSWORD and STOP_IMAP_SUBJECT are configured"
        )
        return 0

    port = int(os.getenv("STOP_IMAP_PORT", "993"))
    folder = os.getenv("STOP_IMAP_FOLDER", "INBOX")

    with imaplib.IMAP4_SSL(host, port) as client:
        client.login(username, password)
        status, _ = client.select(folder)
        if status != "OK":
            raise RuntimeError(f"Cannot select IMAP folder {folder}")

        criteria = ["UNSEEN", "SUBJECT", f'"{subject_filter}"']
        if not _sender_filter_allows_any(sender_filter):
            criteria.extend(["FROM", f'"{sender_filter}"'])
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
                if process_message(raw_message, expected_subject=subject_filter, sender_filter=sender_filter):
                    client.uid("store", uid, "+FLAGS", "(\\Seen)")
                    processed_count += 1
            except Exception:
                log.exception("failed to process IMAP message uid=%s", uid.decode(errors="ignore"))
        return processed_count


def poll_once() -> int:
    provider = os.getenv("STOP_MAIL_PROVIDER", "resend").strip().lower()
    if provider == "resend":
        return poll_resend_once()
    if provider == "imap":
        return poll_imap_once()
    raise RuntimeError("STOP_MAIL_PROVIDER must be 'resend' or 'imap'")


def run_forever() -> None:
    interval = max(60, int(os.getenv("STOP_MAIL_POLL_SECONDS", os.getenv("STOP_IMAP_POLL_SECONDS", "60"))))
    while True:
        try:
            count = poll_once()
            if count:
                log.info("processed %s registry message(s)", count)
        except Exception:
            log.exception("registry mailbox polling error")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import stop registry from XLSB or poll Resend/IMAP mailbox")
    parser.add_argument("--file", help="Import one local XLSB file and exit")
    args = parser.parse_args()
    if args.file:
        print(import_file(args.file))
        return
    run_forever()


if __name__ == "__main__":
    main()
