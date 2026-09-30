#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Paperly supervisor: runs the server + Cloudflare tunnel and keeps them going.
#     bash scripts/start_termux.sh           # server + internet tunnel
#     bash scripts/start_termux.sh --lan     # server only (same Wi-Fi)
#
# - Restarts the server if it stops.
# - Every 10 minutes checks GitHub for updates; installs them and restarts ONLY the
#   server (never the tunnel), and only when nobody's paper is being written.
#   Set AUTO_UPDATE=false in .env to turn this off.
# - Posts the tunnel address (signed) so the app follows address changes by itself.
# Stop everything with Ctrl+C.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${PAPERLY_BACKEND_DIR:-$(dirname "$SCRIPT_DIR")}"

# Run from a private copy: `git pull` may rewrite this file, and bash reads scripts while running them.
if [ -z "$PAPERLY_SUPERVISOR_COPY" ]; then
    COPY="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/paperly_supervisor.sh"
    cp "${BASH_SOURCE[0]}" "$COPY"
    PAPERLY_SUPERVISOR_COPY=1 PAPERLY_BACKEND_DIR="$BACKEND_DIR" exec bash "$COPY" "$@"
fi

cd "$BACKEND_DIR" || exit 1
source .venv/bin/activate

env_value() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs; }
PORT="$(env_value PORT)"; PORT="${PORT:-8000}"
AUTO_UPDATE="$(env_value AUTO_UPDATE)"; AUTO_UPDATE="${AUTO_UPDATE:-true}"
TUNNEL_LOG="$BACKEND_DIR/tunnel.log"
SERVER_LOG="$BACKEND_DIR/server.log"
MODE="${1:-tunnel}"

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

SERVER_PID=""; TUNNEL_PID=""; URL=""

log() { echo "[$(date '+%H:%M:%S')] $*"; }

start_server() {
    uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers --forwarded-allow-ips="*" \
        >> "$SERVER_LOG" 2>&1 &
    SERVER_PID=$!
    for _ in $(seq 1 30); do
        curl -s -m 2 "http://127.0.0.1:$PORT/health" >/dev/null && { log "Server running (port $PORT)."; return 0; }
        sleep 1
    done
    log "Server did not start; last lines of $SERVER_LOG:"; tail -5 "$SERVER_LOG"
}

stop_server() {
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null && wait "$SERVER_PID" 2>/dev/null
    SERVER_PID=""
}

publish() {
    [ -n "$URL" ] && python scripts/publish_url.py "$URL" >/dev/null 2>&1 && LAST_PUBLISH=$(date +%s)
}

start_tunnel() {
    rm -f "$TUNNEL_LOG"
    cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" > "$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    URL=""
    for _ in $(seq 1 45); do
        URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
        [ -n "$URL" ] && break
        sleep 1
    done
    if [ -z "$URL" ]; then
        log "Could not open the tunnel (no internet?). Retrying soon."
        return 1
    fi
    publish
    echo ""
    echo "================================================================"
    echo "  Server address: $URL"
    echo "  Apps that have signed in before switch to it automatically."
    echo "  New phones: Login > Server settings > paste this address."
    echo "================================================================"
    command -v termux-clipboard-set >/dev/null 2>&1 && echo -n "$URL" | termux-clipboard-set 2>/dev/null
}

server_busy() {
    local busy
    busy=$(curl -s -m 3 "http://127.0.0.1:$PORT/health" | grep -o '"busy":[0-9]*' | cut -d: -f2)
    [ -n "$busy" ] && [ "$busy" != "0" ]
}

check_for_update() {
    [ "$AUTO_UPDATE" = "false" ] && return
    git fetch -q origin main 2>/dev/null || return
    [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && return
    if server_busy; then
        log "Update available; waiting until no paper is being written."
        return
    fi
    local req_before req_after
    req_before=$(cat requirements.txt constraints-termux.txt 2>/dev/null | md5sum)
    if ! git pull -q --ff-only origin main; then
        log "Update could not be applied automatically (local changes?). Run: git status"
        return
    fi
    req_after=$(cat requirements.txt constraints-termux.txt 2>/dev/null | md5sum)
    if [ "$req_before" != "$req_after" ]; then
        log "Installing new packages..."
        PIP_EXTRA_INDEX_URL="https://termux-user-repository.github.io/pypi/" \
            pip install -q --prefer-binary -r requirements.txt -c constraints-termux.txt
    fi
    if [ -n "$SERVER_PID" ]; then
        log "Updated to $(git log -1 --format='%h %s' | cut -c1-70). Restarting server (address unchanged)."
        stop_server
        start_server
    else
        log "Updated to $(git log -1 --format='%h %s' | cut -c1-70)."
    fi
}

cleanup() {
    echo ""
    log "Stopping Paperly..."
    [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
    stop_server
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
    exit 0
}
trap cleanup INT TERM

log "Starting Paperly..."
check_for_update
start_server
if [ "$MODE" = "--lan" ]; then
    LAN_IP=$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
    echo "  Server address (same Wi-Fi only): http://${LAN_IP:-<phone-wifi-ip>}:$PORT"
else
    start_tunnel
fi
echo "Leave Termux running. Press Ctrl+C to stop."

LAST_UPDATE_CHECK=$(date +%s)
LAST_PUBLISH=${LAST_PUBLISH:-$(date +%s)}
while true; do
    sleep 30
    now=$(date +%s)
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        log "Server stopped unexpectedly; restarting."
        start_server
    fi
    if [ "$MODE" != "--lan" ]; then
        if ! kill -0 "$TUNNEL_PID" 2>/dev/null || [ -z "$URL" ]; then
            log "Tunnel is down; reopening (the app will pick up the new address)."
            [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
            start_tunnel
        elif [ $((now - LAST_PUBLISH)) -ge 21600 ]; then
            publish  # the notice board keeps messages ~12 h; refresh every 6 h
        fi
    fi
    if [ $((now - LAST_UPDATE_CHECK)) -ge 600 ]; then
        LAST_UPDATE_CHECK=$now
        check_for_update
    fi
done
