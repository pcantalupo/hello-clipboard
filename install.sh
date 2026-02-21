#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PLIST_NAME="com.user.clipboard-monitor"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# Create venv and install deps
python3 -m venv "$VENV_DIR"
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

# Load the agent
launchctl load "$PLIST_DEST"

echo "Installed. Clipboard monitor will start on login."
echo "To run now: $VENV_DIR/bin/python3 $SCRIPT_DIR/clipboard_monitor.py"
