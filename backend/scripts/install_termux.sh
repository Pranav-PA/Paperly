#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Paperly — Termux Environment Setup Script
# Run this inside Termux on your Android phone to set up the Paperly backend.
# ==============================================================================

set -e

echo "=== [1/5] Updating Termux packages & installing system dependencies ==="
pkg update -y
pkg install -y python clang libxml2 libxslt openssl termux-tools git

echo "=== [2/5] Setting up Python virtual environment ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
    python -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip

echo "=== [3/5] Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== [4/5] Configuring environment & database ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created default .env file. Please edit .env with your GEMINI_API_KEY."
fi

# Acquire wake lock so Termux does not sleep when screen turns off
termux-wake-lock

echo "=== [5/5] Initializing Database & Administrator Account ==="
python scripts/manage.py list-users || true

echo "========================================================================"
echo "Paperly setup complete!"
echo "To create your first teacher account, run:"
echo "  source .venv/bin/activate && python scripts/manage.py create-user --username teacher01 --password secret"
echo ""
echo "To start the Paperly server, run:"
echo "  ./scripts/start_termux.sh"
echo "========================================================================"
