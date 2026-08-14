from __future__ import annotations
from email.message import EmailMessage
from pathlib import Path
import smtplib
from ..config import settings


def send_export(recipient: str, subject: str, body: str, attachments: list[Path]) -> str:
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

    if settings.mail_mode.lower() == "file":
        out = Path(settings.outbox_dir)
        out.mkdir(parents=True, exist_ok=True)
        eml = out / f"{attachments[0].stem}.eml"
        eml.write_bytes(msg.as_bytes())
        return f"file:{eml}"

    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST не настроен")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    return "smtp:sent"
