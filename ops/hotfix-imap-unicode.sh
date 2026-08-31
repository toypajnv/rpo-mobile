#!/usr/bin/env bash
set -euo pipefail
cd /opt/rpo
python3 - <<'PY'
from pathlib import Path
p = Path('server/app/ostanovka_worker.py')
s = p.read_text(encoding='utf-8')
old = '        criteria = ["UNSEEN", "SUBJECT", f\'"{subject_filter}"\']\n'
new = '        criteria = ["UNSEEN"]\n'
if old not in s:
    raise SystemExit('Expected IMAP criteria line not found')
p.write_text(s.replace(old, new, 1), encoding='utf-8')
PY
docker compose up -d --build --no-deps ostanovka-mail
docker compose logs --tail=30 ostanovka-mail
