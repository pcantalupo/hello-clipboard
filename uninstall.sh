#!/bin/bash
PLIST_DEST="$HOME/Library/LaunchAgents/com.user.hello-clipboard.plist"
launchctl unload "$PLIST_DEST" 2>/dev/null
pkill -f hello-clipboard 2>/dev/null || true
rm -f "$PLIST_DEST"
echo "Uninstalled. Hello Clipboard will no longer start on login."
