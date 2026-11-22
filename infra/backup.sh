#!/bin/bash
# Nightly backup for the Paragon Radar droplet (R2 item 25). Runs on the host from
# paragon-backup.timer, so it works even when the app container is down.
#
#   1. pg_dump (custom format) of the database   -> /srv/paragon/backups/db/
#   2. the app volume (source evidence, captures) -> /srv/paragon/backups/files.tar.gz (rolling)
#   3. off-box copy to Backblaze B2 with rclone   (when /etc/paragon/backup.env has B2_* keys)
#   4. keep 14 days locally and off-box; ping healthchecks.io when HEALTHCHECK_URL is set
#
# Restore check: infra/backup.sh --restore-check  (restores the newest dump into a scratch DB)
set -euo pipefail
APP=/srv/paragon/app
DEST=/srv/paragon/backups
KEEP_DAYS=14
COMPOSE=(docker compose -f "$APP/infra/compose.yaml")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
umask 077
mkdir -p "$DEST/db"
[ -f /etc/paragon/backup.env ] && set -a && . /etc/paragon/backup.env && set +a

ping() { [ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL$1" >/dev/null || true; }

if [ "${1:-}" = "--restore-check" ]; then
  latest=$(ls -1t "$DEST"/db/*.dump | head -1)
  "${COMPOSE[@]}" exec -T db sh -c 'dropdb -U paragon --if-exists restore_check && createdb -U paragon restore_check'
  "${COMPOSE[@]}" exec -T db pg_restore -U paragon -d restore_check --no-owner < "$latest"
  rows=$("${COMPOSE[@]}" exec -T db psql -U paragon -d restore_check -tAc "select count(*) from locations_location")
  "${COMPOSE[@]}" exec -T db dropdb -U paragon restore_check
  echo "restore check OK: $(basename "$latest") restored with $rows locations"
  exit 0
fi

ping /start
trap 'ping /fail' ERR

# 1. Database
"${COMPOSE[@]}" exec -T db pg_dump -U paragon -d paragon -Fc --no-owner > "$DEST/db/paragon-$STAMP.dump.part"
mv "$DEST/db/paragon-$STAMP.dump.part" "$DEST/db/paragon-$STAMP.dump"

# 2. App files (artifacts are content-addressed; one rolling archive is enough locally)
volume=$(docker volume ls -q --filter name=paragon_appdata | head -1)
docker run --rm -v "$volume":/data:ro -v "$DEST":/out alpine \
  tar -czf /out/files.tar.gz.part -C /data --exclude=./overture-archive --exclude=./duckdb-extensions --exclude=./acs-cache .
mv "$DEST/files.tar.gz.part" "$DEST/files.tar.gz"

# 3. Off-box copy
if [ -n "${B2_KEY_ID:-}" ] && [ -n "${B2_APP_KEY:-}" ] && [ -n "${B2_BUCKET:-}" ]; then
  export RCLONE_CONFIG_B2_TYPE=b2 RCLONE_CONFIG_B2_ACCOUNT="$B2_KEY_ID" RCLONE_CONFIG_B2_KEY="$B2_APP_KEY"
  rclone copy "$DEST/db" "b2:$B2_BUCKET/db" --min-age 0s --transfers 2
  rclone copyto "$DEST/files.tar.gz" "b2:$B2_BUCKET/files/files-$(date -u +%a).tar.gz"   # 7 rotating copies
  rclone delete "b2:$B2_BUCKET/db" --min-age "${KEEP_DAYS}d"
  # The original Overture archive can never be re-downloaded: copy it once, then only changes.
  [ -d /srv/paragon/overture-archive ] && rclone copy /srv/paragon/overture-archive "b2:$B2_BUCKET/overture-archive" --transfers 2
  echo "off-box copy done"
else
  echo "WARNING: no off-box copy (B2_KEY_ID / B2_APP_KEY / B2_BUCKET missing in /etc/paragon/backup.env)" >&2
fi

# 4. Retention
find "$DEST/db" -name '*.dump' -mtime +"$KEEP_DAYS" -delete
echo "backup $STAMP done: $(du -h "$DEST/db/paragon-$STAMP.dump" | cut -f1) database, $(du -h "$DEST/files.tar.gz" | cut -f1) files"
ping ""
