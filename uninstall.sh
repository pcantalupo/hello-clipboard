#!/bin/bash
PLIST_DEST="$HOME/Library/LaunchAgents/com.user.clipboard-monitor.plist"
launchctl unload "$PLIST_DEST" 2>/dev/null
pkill -f clipboard-monitor 2>/dev/null || true
rm -f "$PLIST_DEST"
echo "Uninstalled. Clipboard monitor will no longer start on login."
