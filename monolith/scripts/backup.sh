#!/usr/bin/env bash
# Hy+ Clinic daily backup: database + profile photos, encrypted, copied to Google Drive.
#
#   1. Dump the database and the media files into backups/ (as `make backup`).
#   2. Encrypt both with GPG (AES-256) using the passphrase in ~/.config/hyplus/backup.pass.
#   3. Upload the encrypted files to Google Drive with rclone (remote "gdrive", which can
#      only see the files it created), into the folder REMOTE_DIR.
#   4. Keep LOCAL_DAYS days of backups on the server and REMOTE_DAYS days on Drive.
#
# Steps 2-3 run only once Google Drive is connected (an rclone remote "gdrive" in
# ~/.config/rclone/rclone.conf); until then the backups stay on this server only.
#
# Restore: gpg --decrypt FILE.sql.gz.gpg > FILE.sql.gz, then `make restore FILE=...`.
# Without the passphrase the backups cannot be read: keep a copy of it off this server.
set -euo pipefail

cd "$(dirname "$0")/.."
APP_DIR=$(pwd)
BACKUP_DIR="$APP_DIR/backups"
PASSFILE="${PASSFILE:-$HOME/.config/hyplus/backup.pass}"
RCLONE_CONFIG_DIR="${RCLONE_CONFIG_DIR:-$HOME/.config/rclone}"
RCLONE_IMAGE="${RCLONE_IMAGE:-rclone/rclone:1.75.1}"
REMOTE_DIR="${REMOTE_DIR:-gdrive:HyplusClinic-backups}"
LOCAL_DAYS="${LOCAL_DAYS:-14}"
REMOTE_DAYS="${REMOTE_DAYS:-60}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/hyplus-monitor"

log() { logger -t hyplus-backup "$*"; echo "$(date '+%F %T') $*"; }
fail() { log "FAILED: $*"; exit 1; }
trap 'fail "line $LINENO"' ERR

mkdir -p "$BACKUP_DIR" "$STATE_DIR"
chmod 700 "$BACKUP_DIR"
stamp=$(date +%Y%m%d-%H%M%S)
db="$BACKUP_DIR/aivin-$stamp.sql.gz"
media="$BACKUP_DIR/aivin-media-$stamp.tar.gz"
outbox=$(mktemp -d)
trap 'rm -rf "$outbox"' EXIT

# 1. Dump.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$db"
docker compose exec -T web tar -czf - -C /app media > "$media"
[ -s "$db" ] || fail "empty database dump"
chmod 600 "$db" "$media"

if ! grep -qs '^\[gdrive\]' "$RCLONE_CONFIG_DIR/rclone.conf"; then
    find "$BACKUP_DIR" -maxdepth 1 -name 'aivin-*' -mtime "+$LOCAL_DAYS" -delete
    log "OK: $(basename "$db") and $(basename "$media") (server only; Google Drive is not connected)"
    exit 0
fi
[ -r "$PASSFILE" ] || fail "missing passphrase file $PASSFILE"

# 2. Encrypt.
for file in "$db" "$media"; do
    gpg --batch --yes --quiet --symmetric --cipher-algo AES256 --passphrase-file "$PASSFILE" \
        --output "$outbox/$(basename "$file").gpg" "$file"
done

# 3. Upload, then 4. prune old copies on Drive.
rclone() {
    docker run --rm -u "$(id -u):$(id -g)" -e HOME=/config \
        -v "$RCLONE_CONFIG_DIR:/config/rclone" -v "$outbox:/outbox:ro" "$RCLONE_IMAGE" "$@"
}
rclone copy /outbox "$REMOTE_DIR" --log-level ERROR
rclone delete "$REMOTE_DIR" --min-age "${REMOTE_DAYS}d" --log-level ERROR
date +%s > "$STATE_DIR/offsite_last_success"

# 4. Prune old copies on the server.
find "$BACKUP_DIR" -maxdepth 1 -name 'aivin-*' -mtime "+$LOCAL_DAYS" -delete

log "OK: $(basename "$db") and $(basename "$media") encrypted and uploaded to $REMOTE_DIR"
