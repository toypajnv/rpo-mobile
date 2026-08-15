from __future__ import annotations

import base64
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..config import settings


def _build_message(recipient: str, subject: str, body: str, attachments: list[Path]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = recipient
    msg.set_content(body)

    for path in attachments:
        data = path.read_bytes()
        if path.suffix.lower() == ".xlsx":
            maintype, subtype = "application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            maintype, subtype = "application", "json"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def _send_resend(
    recipient: str,
    subject: str,
    body: str,
    attachments: list[Path],
    idempotency_key: str | None,
) -> str:
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY не настроен")

    payload = {
        "from": settings.resend_from,
        "to": [recipient],
        "subject": subject,
        "text": body,
        "attachments": [
            {
                "filename": path.name,
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
            for path in attachments
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "RPO-Server/1.0",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key[:256]

    req = urllib_request.Request(
        settings.resend_api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Resend API HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Resend API недоступен: {exc.reason}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Resend API вернул некорректный JSON") from exc
    email_id = str(result.get("id", "")).strip()
    if not email_id:
        raise RuntimeError(f"Resend API не вернул ID письма: {raw[:500]}")
    return f"resend:{email_id}"


def send_export(
    recipient: str,
    subject: str,
    body: str,
    attachments: list[Path],
    idempotency_key: str | None = None,
) -> str:
    mode = settings.mail_mode.lower().strip()

    if mode == "resend":
        return _send_resend(recipient, subject, body, attachments, idempotency_key)

    msg = _build_message(recipient, subject, body, attachments)
    if mode == "file":
        out = Path(settings.outbox_dir)
        out.mkdir(parents=True, exist_ok=True)
        eml = out / f"{attachments[0].stem}.eml"
        eml.write_bytes(msg.as_bytes())
        return f"file:{eml}"

    if mode != "smtp":
        raise RuntimeError(f"Неизвестный MAIL_MODE: {settings.mail_mode}")
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST не настроен")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    return "smtp:sent"
