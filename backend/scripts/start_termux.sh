#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Paperly — Termux Server Startup Script
# Keeps device awake and starts Uvicorn single-worker server.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

# Prevent Android CPU sleep
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    echo "[*] Termux WakeLock acquired."
fi

source .venv/bin/activate

echo "[*] Starting Paperly FastAPI server on http://0.0.0.0:8000 ..."
echo "[*] Single-worker mode enabled to preserve CPU thermals and memory on phone."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
