#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Make Paperly start by itself whenever the phone turns on.
# Needs the free "Termux:Boot" app from F-Droid (open it once after installing).
#     bash scripts/setup_autostart.sh
# Logs: ~/paperly.log   ·   Turn off: rm ~/.termux/boot/paperly
# ==============================================================================
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/paperly <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
sleep 20  # give Wi-Fi / mobile data time to connect
cd "$BACKEND_DIR" && bash scripts/start_termux.sh >> ~/paperly.log 2>&1
BOOT
chmod +x ~/.termux/boot/paperly
echo "Done. Paperly will start automatically when the phone boots."
echo "Make sure Termux:Boot (F-Droid) is installed and has been opened once."
echo "See what it's doing any time:  tail -f ~/paperly.log"
