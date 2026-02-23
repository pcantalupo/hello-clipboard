#!/usr/bin/env python3
import io
import tkinter as tk

import objc
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSMenu,
    NSMenuItem,
    NSPasteboard,
    NSPasteboardTypePNG,
    NSPasteboardTypeTIFF,
    NSPasteboardTypeString,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSObject
from PIL import Image, ImageTk


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
        # Ensure NSApplication is initialized; hide from Dock (menu bar only)
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

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
        self.pasteboard = NSPasteboard.generalPasteboard()
        self.last_change_count = self.pasteboard.changeCount()
        self.monitoring = True
        self.root = None
        self.text_widget = None
        self.scrollbar = None
        self.image_label = None
        self.updating_from_clipboard = False
        self.visible = False
        self.menu_bar = None
        self.current_mode = 'text'
        self.current_image = None
        self.current_photo = None

    def get_clipboard_content(self):
        """Return (content_type, data) from the system clipboard."""
        types = self.pasteboard.types()
        if types is None:
            return ('empty', None)

        # Check for image types first
        for img_type in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            if img_type in types:
                data = self.pasteboard.dataForType_(img_type)
                if data:
                    try:
                        pil_image = Image.open(io.BytesIO(data.bytes()))
                        return ('image', pil_image)
                    except Exception:
                        pass

        # Fall back to text
        if NSPasteboardTypeString in types:
            text = self.pasteboard.stringForType_(NSPasteboardTypeString)
            if text:
                return ('text', text)

        return ('empty', None)

    def set_clipboard_text(self, content):
        """Set the system clipboard to text content."""
        self.pasteboard.clearContents()
        self.pasteboard.setString_forType_(content, NSPasteboardTypeString)
        self.last_change_count = self.pasteboard.changeCount()

    def set_clipboard_image(self, pil_image):
        """Set the system clipboard to image content."""
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        from AppKit import NSData
        ns_data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
        self.pasteboard.clearContents()
        self.pasteboard.setData_forType_(ns_data, NSPasteboardTypePNG)
        self.last_change_count = self.pasteboard.changeCount()

    def clear_clipboard(self, event=None):
        """Clear clipboard and switch to empty text view."""
        if self.current_mode != 'image':
            return
        self.pasteboard.clearContents()
        self.last_change_count = self.pasteboard.changeCount()
        self.current_image = None
        self.current_photo = None
        self.show_text_mode(force=True)
        self.updating_from_clipboard = True
        self.text_widget.delete('1.0', tk.END)
        self.updating_from_clipboard = False

    def show_text_mode(self, force=False):
        """Switch UI to text display mode."""
        if self.current_mode == 'text' and not force:
            return
        self.current_mode = 'text'
        self.image_label.pack_forget()
        self.clear_button.pack_forget()
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def show_image_mode(self):
        """Switch UI to image display mode."""
        if self.current_mode == 'image':
            return
        self.current_mode = 'image'
        self.text_widget.pack_forget()
        self.scrollbar.pack_forget()
        self.clear_button.pack(side=tk.BOTTOM, pady=6)
        self.image_label.pack(fill=tk.BOTH, expand=True)

    def update_window(self, content_type, data):
        """Update the window with new clipboard content."""
        if content_type == 'text':
            self.show_text_mode()
            if self.text_widget and not self.updating_from_clipboard:
                self.updating_from_clipboard = True
                self.text_widget.delete('1.0', tk.END)
                self.text_widget.insert('1.0', data)
                self.updating_from_clipboard = False
        elif content_type == 'image':
            self.show_image_mode()
            self.current_image = data
            self._display_image(data)


    def _display_image(self, pil_image):
        """Scale and display a PIL image in the image label."""
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        if win_w < 10 or win_h < 10:
            win_w, win_h = 600, 400

        img = pil_image.copy()
        img.thumbnail((win_w, win_h), Image.LANCZOS)
        self.current_photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=self.current_photo)

    def on_text_change(self, event=None):
        """Called when user edits the text widget."""
        if not self.updating_from_clipboard:
            current_text = self.text_widget.get('1.0', 'end-1c')
            self.set_clipboard_text(current_text)

    def on_text_modified(self, event=None):
        """Handle text modification events."""
        if self.text_widget.edit_modified():
            self.on_text_change()
            self.text_widget.edit_modified(False)

    def check_clipboard(self):
        """Periodically check clipboard and update window."""
        current_count = self.pasteboard.changeCount()
        if current_count != self.last_change_count:
            self.last_change_count = current_count
            content_type, data = self.get_clipboard_content()
            if content_type != 'empty':
                self.update_window(content_type, data)

        if self.monitoring:
            self.root.after(500, self.check_clipboard)

    def show(self):
        """Show the window."""
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.visible = True
            if self.menu_bar:
                self.menu_bar.set_title("Hide Window")

    def hide(self):
        """Hide the window."""
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

    def _on_resize(self, event=None):
        """Re-scale the displayed image when the window is resized."""
        if self.current_mode == 'image' and self.current_image:
            self._display_image(self.current_image)

    def run(self):
        """Create window and start mainloop."""
        self.root = tk.Tk()
        self.root.title("Clipboard Contents")
        self.root.geometry("600x400")

        # Close button hides instead of quitting
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Text widgets
        self.text_widget = tk.Text(self.root, wrap=tk.WORD, font=("Monaco", 12))
        self.scrollbar = tk.Scrollbar(self.root, command=self.text_widget.yview)
        self.text_widget.config(yscrollcommand=self.scrollbar.set)
        self.text_widget.bind('<<Modified>>', self.on_text_modified)

        # Image widget and clear button
        self.image_label = tk.Label(self.root, bg='#2b2b2b')
        self.clear_button = tk.Button(
            self.root, text="Clear", command=self.clear_clipboard,
        )

        # Start in text mode
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial clipboard content
        content_type, data = self.get_clipboard_content()
        if content_type == 'text' and data:
            self.text_widget.insert('1.0', data)
        elif content_type == 'image' and data:
            self.update_window('image', data)

        # Keyboard shortcuts to clear image
        self.root.bind('<Delete>', self.clear_clipboard)
        self.root.bind('<BackSpace>', self.clear_clipboard)

        # Re-scale image on window resize
        self.root.bind('<Configure>', self._on_resize)

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
