#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Paperly: one-time Termux setup. Run from the backend folder:
#     bash scripts/install_termux.sh
# Safe to run again; it skips work that is already done.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

# Prebuilt Android wheels (pydantic-core) so nothing has to compile Rust.
export PIP_EXTRA_INDEX_URL="https://termux-user-repository.github.io/pypi/"
# Needed only if a package has to be compiled with Rust (maturin asks for it).
export ANDROID_API_LEVEL="$(getprop ro.build.version.sdk 2>/dev/null || echo 24)"

echo ""
echo "Phone: Android $(getprop ro.build.version.release 2>/dev/null || echo '?'), CPU $(uname -m)"
echo ""

echo "=== [1/5] Installing system packages (takes a few minutes) ==="
pkg update -y
pkg install -y python clang make pkg-config libxml2 libxslt libjpeg-turbo freetype zlib cloudflared termux-tools
# Ready-made Termux builds of Pillow and lxml (otherwise pip compiles them, which is slow but works).
pkg install -y python-pillow || true
pkg install -y python-lxml || true
# Unicode fonts so PDFs show symbols like π, √, θ, ² instead of boxes.
pkg install -y ttf-dejavu || true

echo "=== [2/5] Creating Python environment ==="
# --system-site-packages lets the venv use the Termux Pillow/lxml installed above.
if [ -d ".venv" ] && ! grep -q "include-system-site-packages = true" .venv/pyvenv.cfg; then
    rm -rf .venv
fi
if [ ! -d ".venv" ]; then
    python -m venv --system-site-packages .venv
fi
source .venv/bin/activate
pip install --upgrade pip wheel setuptools

echo "=== [3/5] Installing Paperly's Python packages ==="
if ! pip install --prefer-binary -r requirements.txt -c constraints-termux.txt; then
    echo ""
    echo "No prebuilt package for this phone's CPU; installing the Rust compiler and building instead."
    echo "This can take 20-40 minutes on an old phone. Keep Termux open and the phone charging."
    pkg install -y rust binutils
    pip install --prefer-binary -r requirements.txt -c constraints-termux.txt
fi

echo "=== [4/5] Configuring Gemini ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
fi
if grep -q "^GEMINI_API_KEY=your_gemini_api_key_here" .env; then
    echo "Paste your Gemini API key (from https://aistudio.google.com/apikey) and press Enter."
    echo "Leave empty to skip and edit backend/.env later."
    read -r -p "GEMINI_API_KEY: " GEMINI_KEY
    if [ -n "$GEMINI_KEY" ]; then
        sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=${GEMINI_KEY}|" .env
    fi
fi

echo "=== [5/5] Creating login accounts ==="
if [ ! -f "credentials.txt" ]; then
    python scripts/manage.py seed-accounts --count 10
else
    echo "credentials.txt already exists; keeping existing accounts."
fi

echo ""
python scripts/manage.py check-gemini || true

echo ""
echo "========================================================================"
echo " Paperly setup complete!"
echo ""
echo "  Logins:        cat credentials.txt"
echo "  Start server:  bash scripts/start_termux.sh"
echo "========================================================================"
