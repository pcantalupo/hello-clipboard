#!/usr/bin/env python3
import tkinter as tk
import subprocess
import objc
from Foundation import NSObject
from AppKit import (
    NSStatusBar, NSMenu, NSMenuItem, NSVariableStatusItemLength,
    NSApplication,
)


class MenuBarDelegate(NSObject):
    """NSObject subclass so macOS recognizes the action targets."""

    def initWithCallbacks_(self, callbacks):
        self = objc.super(MenuBarDelegate, self).init()
        if self is None:
            return None
        self.on_toggle = callbacks["on_toggle"]
        self.on_quit = callbacks["on_quit"]
        return self

    @objc.typedSelector(b"v@:@")
    def toggleWindow_(self, sender):
        self.on_toggle()

    @objc.typedSelector(b"v@:@")
    def quitApp_(self, sender):
        self.on_quit()


class MenuBarIcon:
    """macOS menu bar icon using PyObjC — works alongside Tkinter."""

    def __init__(self, on_toggle, on_quit):
        # Ensure NSApplication is initialized
        NSApplication.sharedApplication()

        # Create delegate (must be NSObject subclass for target/action)
        self.delegate = MenuBarDelegate.alloc().initWithCallbacks_({
            "on_toggle": on_toggle,
            "on_quit": on_quit,
        })

        # Create status bar item
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self.status_item.setTitle_("📋")
        self.status_item.setHighlightMode_(True)

        # Build menu
        menu = NSMenu.alloc().init()

        show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Window", "toggleWindow:", ""
        )
        show_item.setTarget_(self.delegate)
        menu.addItem_(show_item)
        self.show_item = show_item

        menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", ""
        )
        quit_item.setTarget_(self.delegate)
        menu.addItem_(quit_item)

        self.status_item.setMenu_(menu)

    def set_title(self, title):
        self.show_item.setTitle_(title)


class ClipboardWindow:
    """Tkinter window for clipboard editing."""

    def __init__(self):
        self.last_content = ""
        self.monitoring = True
        self.root = None
        self.text_widget = None
        self.updating_from_clipboard = False
        self.visible = False
        self.menu_bar = None

    def get_clipboard_text(self):
        try:
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            return result.stdout
        except:
            return ""

    def set_clipboard_text(self, content):
        """Set the system clipboard"""
        try:
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            process.communicate(content.encode('utf-8'))
        except:
            pass

    def update_window(self, content):
        """Update the text widget with new content from external copy"""
        if self.text_widget and not self.updating_from_clipboard:
            self.updating_from_clipboard = True
            self.text_widget.delete('1.0', tk.END)
            self.text_widget.insert('1.0', content)
            self.updating_from_clipboard = False

            if self.visible:
                self.root.lift()
                self.root.attributes('-topmost', True)
                self.root.after_idle(self.root.attributes, '-topmost', False)

    def on_text_change(self, event=None):
        """Called when user edits the text widget"""
        if not self.updating_from_clipboard:
            current_text = self.text_widget.get('1.0', 'end-1c')
            self.set_clipboard_text(current_text)
            self.last_content = current_text

    def on_text_modified(self, event=None):
        """Handle text modification events"""
        if self.text_widget.edit_modified():
            self.on_text_change()
            self.text_widget.edit_modified(False)

    def check_clipboard(self):
        """Periodically check clipboard and update window"""
        current = self.get_clipboard_text()

        if current != self.last_content and current.strip():
            self.last_content = current
            self.update_window(current)

        if self.monitoring:
            self.root.after(500, self.check_clipboard)

    def show(self):
        """Show the window"""
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.visible = True
            if self.menu_bar:
                self.menu_bar.set_title("Hide Window")

    def hide(self):
        """Hide the window"""
        if self.root:
            self.root.withdraw()
            self.visible = False
            if self.menu_bar:
                self.menu_bar.set_title("Show Window")

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def quit_app(self):
        self.monitoring = False
        if self.root:
            self.root.quit()

    def run(self):
        """Create window and start mainloop."""
        self.root = tk.Tk()
        self.root.title("Clipboard Contents")
        self.root.geometry("600x400")

        # Close button hides instead of quitting
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self.text_widget = tk.Text(self.root, wrap=tk.WORD, font=("Monaco", 12))
        scrollbar = tk.Scrollbar(self.root, command=self.text_widget.yview)
        self.text_widget.config(yscrollcommand=scrollbar.set)

        initial_content = self.get_clipboard_text()
        if initial_content:
            self.last_content = initial_content
            self.text_widget.insert('1.0', initial_content)

        self.text_widget.bind('<<Modified>>', self.on_text_modified)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add menu bar icon
        self.menu_bar = MenuBarIcon(
            on_toggle=self.toggle,
            on_quit=self.quit_app,
        )

        self.root.after(500, self.check_clipboard)

        # Start hidden — user opens via menu bar icon
        self.hide()

        self.root.mainloop()


if __name__ == "__main__":
    window = ClipboardWindow()
    window.run()
