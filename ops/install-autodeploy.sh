#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/opt/rpo"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

cd "$PROJECT_DIR"
chmod 0755 ops/autodeploy.sh
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
