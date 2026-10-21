#!/usr/bin/env bash
# Hy+ Clinic watchdog: run every 5 minutes from cron.
#
# Checks the public site, the containers, the BLE gateway, disk space and the
# age of the last backup. It alerts only when a check changes state (fails or
# recovers), so a problem is reported once, not every 5 minutes.
#
# Alerts always go to syslog (journalctl -t hyplus-monitor) and logs/monitor.log.
# To also get them on Telegram, create scripts/monitor.env (chmod 600) with:
#   TELEGRAM_BOT_TOKEN=123456:ABC...
#   TELEGRAM_CHAT_ID=123456789
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
APP_DIR=$(pwd)
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/hyplus-monitor"
LOG_FILE="$APP_DIR/logs/monitor.log"
mkdir -p "$STATE_DIR" "$APP_DIR/logs"

[ -f scripts/monitor.env ] && . scripts/monitor.env
PUBLIC_URL=$(grep -E '^PUBLIC_BASE_URL=' .env | cut -d= -f2-)
LOCAL_URL="http://127.0.0.1:$(grep -E '^AIVIN_PORT=' .env | cut -d= -f2- || true)"
[ "$LOCAL_URL" = "http://127.0.0.1:" ] && LOCAL_URL="http://127.0.0.1:8010"
DISK_LIMIT=${DISK_LIMIT:-85}
BACKUP_MAX_AGE_HOURS=${BACKUP_MAX_AGE_HOURS:-26}

notify() {
    local message="[Hy+ Clinic] $1"
    logger -t hyplus-monitor "$message"
    echo "$(date '+%F %T') $message" >> "$LOG_FILE"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -fsS -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=${message}" > /dev/null \
            || logger -t hyplus-monitor "Telegram alert failed"
    fi
}

# check NAME OK_FLAG DETAIL: alert when NAME changes between ok and failing.
check() {
    local name=$1 ok=$2 detail=$3 file="$STATE_DIR/$1" previous="ok"
    [ -f "$file" ] && previous=$(cat "$file")
    if [ "$ok" = 1 ] && [ "$previous" != ok ]; then
        notify "RECOVERED: $name ($detail)"
        echo ok > "$file"
    elif [ "$ok" != 1 ] && [ "$previous" = ok ]; then
        notify "PROBLEM: $name: $detail"
        echo failing > "$file"
    fi
}

# 1. The public site answers through Cloudflare, and the app is ready (database + cache).
code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$PUBLIC_URL/healthz/")
check public_site "$([ "$code" = 200 ] && echo 1 || echo 0)" "$PUBLIC_URL/healthz/ returned HTTP $code"
code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$LOCAL_URL/healthz/")
check app_ready "$([ "$code" = 200 ] && echo 1 || echo 0)" "app health check returned HTTP $code"

# 2. Containers are running (and the web container reports healthy).
for service in db web gateway; do
    state=$(docker compose ps --format '{{.State}} {{.Health}}' "$service" 2>/dev/null | head -1)
    ok=0
    case "$state" in running*) ok=1 ;; esac
    [ "$service" != gateway ] && [[ "$state" == *unhealthy* ]] && ok=0
    check "container_$service" "$ok" "container '$service' is '${state:-missing}'"
done

# 3. The BLE gateway reports in (needed to read the medical devices).
status=$(docker compose exec -T web python manage.py monitor_status 2>/dev/null | tail -1)
gateway=$(echo "$status" | jq -r '.gateway_online // empty' 2>/dev/null)
check gateway "$([ "$gateway" = true ] && echo 1 || echo 0)" "BLE gateway online: ${gateway:-unknown}"

# 4. Disk space.
used=$(df --output=pcent / | tail -1 | tr -dc '0-9')
check disk "$([ "$used" -lt "$DISK_LIMIT" ] && echo 1 || echo 0)" "disk ${used}% full (limit ${DISK_LIMIT}%)"

# 5. A recent backup exists.
newest=$(ls -t backups/aivin-*.sql.gz 2>/dev/null | head -1)
if [ -n "$newest" ]; then
    age_hours=$(( ($(date +%s) - $(stat -c %Y "$newest")) / 3600 ))
    check backup "$([ "$age_hours" -lt "$BACKUP_MAX_AGE_HOURS" ] && echo 1 || echo 0)" "last backup $age_hours h ago ($(basename "$newest"))"
else
    check backup 0 "no backup found"
fi

# 6. The encrypted copy reached Google Drive (scripts/backup.sh writes this marker).
marker="$STATE_DIR/offsite_last_success"
if [ -f "$marker" ]; then
    age_hours=$(( ($(date +%s) - $(cat "$marker")) / 3600 ))
    check offsite_backup "$([ "$age_hours" -lt "$BACKUP_MAX_AGE_HOURS" ] && echo 1 || echo 0)" "last upload to Google Drive $age_hours h ago"
fi

# Keep the watchdog's own log short.
tail -n 2000 "$LOG_FILE" > "$LOG_FILE.tmp" 2>/dev/null && mv "$LOG_FILE.tmp" "$LOG_FILE"
exit 0
