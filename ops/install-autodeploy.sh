#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/opt/rpo"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

cd "$PROJECT_DIR"

# Do not chmod tracked repository files here. Changing the executable bit makes
# a clean checkout appear locally modified and intentionally stops autodeploy.
# The systemd unit invokes the script explicitly through /bin/bash instead.
install -m 0644 ops/rpo-autodeploy.service /etc/systemd/system/rpo-autodeploy.service
install -m 0644 ops/rpo-autodeploy.timer /etc/systemd/system/rpo-autodeploy.timer
systemctl daemon-reload
systemctl enable --now rpo-autodeploy.timer

# Run once immediately instead of waiting for the first timer tick.
systemctl start rpo-autodeploy.service

echo
systemctl --no-pager --full status rpo-autodeploy.timer || true
echo
systemctl --no-pager --full status rpo-autodeploy.service || true
