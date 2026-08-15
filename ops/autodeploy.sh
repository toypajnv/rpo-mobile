#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="/opt/rpo"
BACKUP_DIR="$PROJECT_DIR/backups/autodeploy"
LOCK_FILE="/run/lock/rpo-autodeploy.lock"
HEALTH_URL="http://127.0.0.1:8000/health"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
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

mkdir -p "$(dirname "$LOCK_FILE")" "$BACKUP_DIR"
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

# Runtime files are ignored; tracked source files must remain clean so an
# automatic deployment never overwrites a manual hotfix silently.
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "ERROR: tracked local changes detected. Automatic deployment stopped."
  git status --short
  exit 1
fi

git fetch --quiet origin main
CURRENT_SHA="$(git rev-parse HEAD)"
TARGET_SHA="$(git rev-parse origin/main)"

if [[ "$CURRENT_SHA" == "$TARGET_SHA" ]]; then
  exit 0
fi

log "Deploying $CURRENT_SHA -> $TARGET_SHA"

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
  git reset --hard "$CURRENT_SHA"
  docker compose up -d --build
  if healthcheck; then
    log "Rollback completed and health check is OK."
  else
    log "CRITICAL: rollback health check also failed."
  fi
}

trap 'rollback' ERR

git checkout -q main
git merge --ff-only origin/main

docker compose up -d --build

if ! healthcheck; then
  log "ERROR: health check failed after deployment."
  false
fi

trap - ERR
log "Deployment successful: $(git rev-parse --short HEAD)"

# Keep two weeks of automatic SQL backups.
find "$BACKUP_DIR" -type f -name 'rpo_*.sql.gz' -mtime +14 -delete || true
