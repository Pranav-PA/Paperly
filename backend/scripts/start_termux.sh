#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Paperly: start the server and a Cloudflare tunnel, then print the URL
# to paste into the app's "Server URL" field.
#     bash scripts/start_termux.sh           # server + internet tunnel
#     bash scripts/start_termux.sh --lan     # server only (same Wi-Fi)
# Stop everything with Ctrl+C.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

PORT="${PORT:-8000}"
TUNNEL_LOG="$BACKEND_DIR/tunnel.log"

# Keep the CPU awake while the screen is off.
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

source .venv/bin/activate

cleanup() {
    echo ""
    echo "Stopping Paperly..."
    [ -n "$TUNNEL_PID" ] && kill "$TUNNEL_PID" 2>/dev/null
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
    exit 0
}
trap cleanup INT TERM

echo "[*] Starting Paperly server on port $PORT ..."
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers --forwarded-allow-ips="*" &
SERVER_PID=$!
sleep 3

if [ "$1" = "--lan" ]; then
    LAN_IP=$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
    echo ""
    echo "================================================================"
    echo "  Server URL for the app (same Wi-Fi only):"
    echo "  http://${LAN_IP:-<phone-wifi-ip>}:$PORT"
    echo "================================================================"
    wait "$SERVER_PID"
    exit 0
fi

echo "[*] Opening Cloudflare tunnel ..."
rm -f "$TUNNEL_LOG"
cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

URL=""
for _ in $(seq 1 30); do
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
    [ -n "$URL" ] && break
    sleep 1
done

echo ""
if [ -n "$URL" ]; then
    echo "================================================================"
    echo "  Server URL for the app (works from anywhere):"
    echo ""
    echo "  $URL"
    echo ""
    echo "  In the app: Login screen > Server settings > paste this URL."
    echo "  Note: this URL changes every time you restart this script."
    echo "================================================================"
    command -v termux-clipboard-set >/dev/null 2>&1 && echo -n "$URL" | termux-clipboard-set 2>/dev/null
else
    echo "Could not get a tunnel URL. Check the phone's internet, then see $TUNNEL_LOG"
fi
echo ""
echo "Leave Termux running. Press Ctrl+C to stop."
wait "$SERVER_PID"
cleanup
