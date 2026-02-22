#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PLIST_NAME="com.user.clipboard-monitor"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# Find a suitable Python (3.10+); the macOS system Python 3.9 is too old for pyobjc 12+
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    path="$(command -v "$candidate" 2>/dev/null)" || continue
    ver="$("$path" -c 'import sys; print(sys.version_info.minor)')"
    if [ "$ver" -ge 10 ] 2>/dev/null; then
        PYTHON="$path"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10 or later is required, but only the system Python 3.9 was found."
    echo "Install a newer Python with Homebrew:  brew install python@3.12"
    exit 1
fi

echo "Using Python: $PYTHON ($("$PYTHON" --version))"

# Create venv and install deps (--clear ensures a stale venv from a different Python is replaced)
"$PYTHON" -m venv --clear "$VENV_DIR"
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# Generate plist with correct paths
cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python3</string>
        <string>$SCRIPT_DIR/clipboard_monitor.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/clipboard-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/clipboard-monitor.err</string>
</dict>
</plist>
EOF

# Load the agent (unload first in case of re-install)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Installed. Clipboard monitor will start on login."
echo "To run now: $VENV_DIR/bin/python3 $SCRIPT_DIR/clipboard_monitor.py"
