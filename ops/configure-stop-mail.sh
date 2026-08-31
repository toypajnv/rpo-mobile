#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${RPO_ROOT:-/opt/rpo}"
ENV_FILE="$ROOT_DIR/.env"
MAILBOX="ostanovka@rpo-mng.ru"
IMAP_HOST="imap.timeweb.ru"
IMAP_PORT="993"
IMAP_FOLDER="INBOX"
SUBJECT="Реестр остановок"
POLL_SECONDS="60"

if [[ ! -d "$ROOT_DIR" ]]; then
  echo "Ошибка: каталог $ROOT_DIR не найден." >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/docker-compose.yml" ]]; then
  echo "Ошибка: $ROOT_DIR/docker-compose.yml не найден." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Ошибка: $ENV_FILE не найден. Сначала должен быть настроен основной сервер РПО." >&2
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Запустите этот скрипт через sudo: sudo bash $ROOT_DIR/ops/configure-stop-mail.sh" >&2
  exit 1
fi

printf 'Настройка входящей почты реестра остановок\n'
printf 'Ящик: %s\n' "$MAILBOX"
printf 'IMAP: %s:%s SSL/TLS\n\n' "$IMAP_HOST" "$IMAP_PORT"

read -r -p "Email доверенного отправителя реестра: " STOP_SENDER
STOP_SENDER="${STOP_SENDER//[[:space:]]/}"
if [[ ! "$STOP_SENDER" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
  echo "Ошибка: некорректный email отправителя." >&2
  exit 1
fi

read -r -s -p "Пароль ящика $MAILBOX: " STOP_PASSWORD
printf '\n'
if [[ -z "$STOP_PASSWORD" ]]; then
  echo "Ошибка: пароль не может быть пустым." >&2
  exit 1
fi

printf 'Проверяю вход в Timeweb IMAP...\n'
STOP_PASSWORD="$STOP_PASSWORD" python3 - <<'PY'
import imaplib
import os
import ssl
import sys

host = "imap.timeweb.ru"
port = 993
username = "ostanovka@rpo-mng.ru"
password = os.environ["STOP_PASSWORD"]

try:
    context = ssl.create_default_context()
    with imaplib.IMAP4_SSL(host, port, ssl_context=context) as client:
        status, _ = client.login(username, password)
        if status != "OK":
            raise RuntimeError("login failed")
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("INBOX unavailable")
except Exception as exc:
    print(f"Ошибка подключения к IMAP: {exc}", file=sys.stderr)
    sys.exit(1)

print("IMAP подключение успешно.")
PY

BACKUP="$ENV_FILE.backup-$(date +%Y%m%d-%H%M%S)"
cp -a "$ENV_FILE" "$BACKUP"
printf 'Резервная копия .env: %s\n' "$BACKUP"

STOP_PASSWORD="$STOP_PASSWORD" STOP_SENDER="$STOP_SENDER" ENV_FILE="$ENV_FILE" python3 - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["ENV_FILE"])
updates = {
    "STOP_MAIL_PROVIDER": "imap",
    "STOP_MAIL_POLL_SECONDS": "60",
    "STOP_IMAP_HOST": "imap.timeweb.ru",
    "STOP_IMAP_PORT": "993",
    "STOP_IMAP_USERNAME": "ostanovka@rpo-mng.ru",
    "STOP_IMAP_PASSWORD": os.environ["STOP_PASSWORD"],
    "STOP_IMAP_FOLDER": "INBOX",
    "STOP_IMAP_SENDER": os.environ["STOP_SENDER"],
    "STOP_IMAP_SUBJECT": "Реестр остановок",
    "STOP_IMAP_POLL_SECONDS": "60",
}

lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        out.append(line)
        continue
    key = line.split("=", 1)[0].strip()
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

if out and out[-1] != "":
    out.append("")
out.append("# Incoming stop registry mailbox (Timeweb IMAP)")
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

unset STOP_PASSWORD
chmod 600 "$ENV_FILE"

cd "$ROOT_DIR"
printf 'Перезапускаю только сервис ostanovka-mail...\n'
docker compose up -d --build --no-deps ostanovka-mail

printf '\nСостояние сервиса:\n'
docker compose ps ostanovka-mail

printf '\nПоследние сообщения сервиса:\n'
docker compose logs --tail=30 ostanovka-mail || true

printf '\nГотово.\n'
printf 'Отправляйте файл на: %s\n' "$MAILBOX"
printf 'Тема письма: %s\n' "$SUBJECT"
printf 'Разрешенный отправитель: %s\n' "$STOP_SENDER"
printf 'Сервер проверяет почту примерно раз в %s секунд.\n' "$POLL_SECONDS"
