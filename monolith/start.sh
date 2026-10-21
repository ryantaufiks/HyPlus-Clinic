#!/usr/bin/env bash
# Hy+ Clinic: start, restart and check the application.
#
#   ./start.sh            start everything (or restart it) and wait until it is healthy
#   ./start.sh rebuild    back up, rebuild with the latest code, then start (database migrations run automatically)
#   ./start.sh stop       stop everything (data is kept)
#   ./start.sh status     show containers and health
#   ./start.sh logs       follow the application log (Ctrl+C to leave)
set -euo pipefail
cd "$(dirname "$0")"

PORT=$(grep -E '^AIVIN_PORT=' .env 2>/dev/null | cut -d= -f2- || true)
LOCAL_URL="http://127.0.0.1:${PORT:-8010}/healthz/"
PUBLIC_URL="$(grep -E '^PUBLIC_BASE_URL=' .env 2>/dev/null | cut -d= -f2- || true)"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

wait_healthy() {
    say "Waiting for the app to be ready…"
    for _ in $(seq 1 60); do
        if curl -fs -m 3 "$LOCAL_URL" > /dev/null 2>&1; then
            say "Ready: $LOCAL_URL"
            [ -n "$PUBLIC_URL" ] && say "Public: $PUBLIC_URL ($(curl -s -o /dev/null -m 15 -w '%{http_code}' "$PUBLIC_URL/healthz/"))"
            return 0
        fi
        sleep 2
    done
    echo "The app did not become healthy within 2 minutes. Recent log:" >&2
    docker compose logs --tail 40 web >&2
    return 1
}

status() {
    docker compose ps --format '{{.Service}}\t{{.State}}\t{{.Status}}' | column -t -s $'\t' -N SERVICE,STATE,STATUS
    curl -s -m 5 "$LOCAL_URL" && echo
}

case "${1:-start}" in
    start|restart)
        say "Starting Hy+ Clinic…"
        docker compose up -d
        docker compose restart web gateway
        wait_healthy
        status
        ;;
    rebuild)
        say "Backing up before the rebuild…"
        make backup
        say "Rebuilding with the latest code…"
        docker compose build
        docker compose up -d
        wait_healthy
        status
        ;;
    stop)
        say "Stopping Hy+ Clinic (data is kept)…"
        docker compose stop
        ;;
    status)
        status
        ;;
    logs)
        docker compose logs -f --tail 100 web
        ;;
    help|-h|--help)
        sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
        ;;
    *)
        echo "Unknown command: $1" >&2
        sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2
        exit 1
        ;;
esac
