# Clipboard Monitor

A macOS menu bar app that monitors your clipboard and lets you view and edit its contents in a floating window.

## What it does

- Adds a clipboard icon (📋) to your macOS menu bar
- Polls the system clipboard every 500ms for changes
- Opens an editable text window where you can view and modify clipboard contents — edits are written back to the clipboard in real time
- Displays copied images with scaling to fit the window
- Closing the window hides it (use the menu bar icon to reopen, or "Quit" to exit)

## Requirements

- macOS
- Python 3.10+ (the built-in macOS system Python 3.9 is **not** supported)
  - Install via [Homebrew](https://brew.sh): `brew install python@3.12`

## Installation

```bash
git clone <repo-url>
cd clipboard
./install.sh
```

### What `install.sh` does

| Step | Detail |
|------|--------|
| Creates `.venv/` | A Python virtual environment inside the project directory |
| Installs dependencies | Runs `pip install -r requirements.txt` into the venv (`pyobjc-framework-Cocoa`) |
| Generates LaunchAgent plist | Writes `com.user.clipboard-monitor.plist` to `~/Library/LaunchAgents/` with paths resolved to your machine |
| Loads the agent | Calls `launchctl load` so the monitor starts on login |

### Files installed outside the repo

| File | Location | Purpose |
|------|----------|---------|
| `com.user.clipboard-monitor.plist` | `~/Library/LaunchAgents/` | macOS LaunchAgent that auto-starts the monitor on login |
| `clipboard-monitor.log` | `/tmp/` | stdout log |
| `clipboard-monitor.err` | `/tmp/` | stderr log |

### Generated plist contents

The plist points to the venv's Python and the monitor script using absolute paths derived at install time:

```xml
<key>ProgramArguments</key>
<array>
    <string>/path/to/clipboard/.venv/bin/python3</string>
    <string>/path/to/clipboard/clipboard_monitor.py</string>
</array>
```

### "Background Items Added" notification

After installation, macOS will show a notification saying **"python3" is an item that can run in the background**. This is expected — it's the clipboard monitor's LaunchAgent. You can review it in **System Settings > General > Login Items & Extensions**.

## Usage

After installation, the monitor starts automatically on login. To interact with it:

- **Open the window** — click the 📋 icon in the menu bar, then "Show Window"
- **Edit clipboard text** — type in the window; changes are written back to the clipboard immediately
- **View clipboard images** — copied images are displayed scaled to fit the window
- **Clear an image** — click the "Clear" button or press Delete/Backspace while viewing an image
- **Hide the window** — close it or click "Hide Window" in the menu bar
- **Quit** — click "Quit" in the menu bar

### Run manually (without LaunchAgent)

```bash
# Using the venv directly
.venv/bin/python3 clipboard_monitor.py

# Or activate the venv first
source .venv/bin/activate
python3 clipboard_monitor.py
```

### Check logs

```bash
cat /tmp/clipboard-monitor.log
cat /tmp/clipboard-monitor.err
```

## Uninstallation

```bash
./uninstall.sh
```

This unloads the LaunchAgent and removes the plist from `~/Library/LaunchAgents/`. The project directory and venv are left intact.

## Project structure

```
clipboard/
├── clipboard_monitor.py   # Main application (pure AppKit, no tkinter)
├── requirements.txt       # Python dependencies (pyobjc-framework-Cocoa)
├── install.sh             # Sets up venv, deps, and LaunchAgent
├── uninstall.sh           # Removes LaunchAgent
└── .venv/                 # Created by install.sh (not committed)
```
