#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/opt/rpo"
BACKUP_DIR="$PROJECT_DIR/backups/autodeploy"
STATE_DIR="/var/lib/rpo-autodeploy"
STATE_FILE="$STATE_DIR/last_successful_sha"
LOCK_FILE="/run/lock/rpo-autodeploy.lock"
HEALTH_URL="http://127.0.0.1:8000/health"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

git_safe() {
  git -c safe.directory="$PROJECT_DIR" "$@"
}

healthcheck() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

mkdir -p "$(dirname "$LOCK_FILE")" "$BACKUP_DIR" "$STATE_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Another deployment is already running; skipping."
  exit 0
fi

cd "$PROJECT_DIR"

if [[ ! -d .git ]]; then
  log "ERROR: $PROJECT_DIR is not a git repository."
  exit 1
fi

# systemd starts this service as root while /opt/rpo is owned by the rpo user.
# Use an explicit safe.directory only for this repository instead of weakening
# Git ownership checks globally.
if ! git_safe diff --quiet || ! git_safe diff --cached --quiet; then
  log "ERROR: tracked local changes detected. Automatic deployment stopped."
  git_safe status --short
  exit 1
fi

git_safe fetch --quiet origin main
CURRENT_SHA="$(git_safe rev-parse HEAD)"
TARGET_SHA="$(git_safe rev-parse origin/main)"
DEPLOYED_SHA="$(cat "$STATE_FILE" 2>/dev/null || true)"

if [[ "$DEPLOYED_SHA" == "$TARGET_SHA" ]]; then
  exit 0
fi

log "Deploying ${DEPLOYED_SHA:-not-yet-recorded} -> $TARGET_SHA (worktree: $CURRENT_SHA)"

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/rpo_${STAMP}_${CURRENT_SHA:0:8}.sql.gz"

if docker compose ps --status running db 2>/dev/null | grep -q 'rpo-db'; then
  log "Creating PostgreSQL backup: $BACKUP_FILE"
  docker compose exec -T db pg_dump -U rpo -d rpo | gzip -9 > "$BACKUP_FILE"
else
  log "WARNING: database container is not reported as running; continuing without DB backup."
fi

rollback() {
  log "Deployment failed; rolling source back to $CURRENT_SHA"
  git_safe reset --hard "$CURRENT_SHA"
  docker compose up -d --build
  if healthcheck; then
    log "Rollback completed and health check is OK."
  else
    log "CRITICAL: rollback health check also failed."
  fi
}

trap 'rollback' ERR

git_safe checkout -q main
if [[ "$(git_safe rev-parse HEAD)" != "$TARGET_SHA" ]]; then
  git_safe merge --ff-only origin/main
fi

docker compose up -d --build

if ! healthcheck; then
  log "ERROR: health check failed after deployment."
  false
fi

trap - ERR
printf '%s\n' "$TARGET_SHA" > "$STATE_FILE"
log "Deployment successful: $(git_safe rev-parse --short HEAD)"

# Keep two weeks of automatic SQL backups.
find "$BACKUP_DIR" -type f -name 'rpo_*.sql.gz' -mtime +14 -delete || true
