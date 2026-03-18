#!/usr/bin/env python3
import datetime
import objc
import signal
from AppKit import (
    NSAlert,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSBezierPath,
    NSButton,
    NSClosableWindowMask,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSImage,
    NSImageScaleProportionallyUpOrDown,
    NSImageView,
    NSMenu,
    NSMenuItem,
    NSMiniaturizableWindowMask,
    NSNotificationCenter,
    NSOffState,
    NSOnState,
    NSPasteboard,
    NSPasteboardTypePNG,
    NSPasteboardTypeTIFF,
    NSPasteboardTypeString,
    NSResizableWindowMask,
    NSScrollView,
    NSStatusBar,
    NSTitledWindowMask,
    NSTextView,
    NSVariableStatusItemLength,
    NSFloatingWindowLevel,
    NSWindow,
)
from Foundation import NSAttributedString, NSMakeRect, NSObject, NSTimer
from detection import check_for_suspicious_content


NSTextDidChangeNotification = "NSTextDidChangeNotification"


MAX_HISTORY_SIZE = 25

# Auto-clear interval choices: (label, seconds). 0 = disabled.
AUTO_CLEAR_INTERVALS = [
    ("Disabled", 0),
    ("30 Seconds", 30),
    ("5 Minutes", 300),
    ("1 Hour", 3600),
    ("24 Hours", 86400),
]


class MenuBarDelegate(NSObject):
    """NSObject subclass so macOS recognizes the action targets."""

    def initWithCallbacks_(self, callbacks):
        self = objc.super(MenuBarDelegate, self).init()
        if self is None:
            return None
        self.on_toggle = callbacks["on_toggle"]
        self.on_quit = callbacks["on_quit"]
        self.on_clear = callbacks["on_clear"]
        self.on_set_auto_clear = callbacks["on_set_auto_clear"]
        self.on_restore_history_item = callbacks["on_restore_history_item"]
        self.on_clear_history = callbacks["on_clear_history"]
        return self

    @objc.typedSelector(b"v@:@")
    def toggleWindow_(self, sender):
        self.on_toggle()

    @objc.typedSelector(b"v@:@")
    def clearClipboard_(self, sender):
        self.on_clear(None)

    @objc.typedSelector(b"v@:@")
    def quitApp_(self, sender):
        self.on_quit()

    @objc.typedSelector(b"v@:@")
    def setAutoClearInterval_(self, sender):
        seconds = sender.representedObject()
        self.on_set_auto_clear(seconds)
        # Update checkmarks in the submenu
        for item in sender.menu().itemArray():
            item.setState_(NSOnState if item == sender else NSOffState)

    @objc.typedSelector(b"v@:@")
    def restoreHistoryItem_(self, sender):
        index = sender.representedObject()
        self.on_restore_history_item(index)

    @objc.typedSelector(b"v@:@")
    def clearHistory_(self, sender):
        self.on_clear_history()


class MenuBarIcon:
    """macOS menu bar icon using PyObjC."""

    _ICON_SIZE = 18.0

    def __init__(self, on_toggle, on_quit, on_clear, on_set_auto_clear,
                 on_restore_history_item, on_clear_history):
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self.delegate = MenuBarDelegate.alloc().initWithCallbacks_({
            "on_toggle": on_toggle,
            "on_quit": on_quit,
            "on_clear": on_clear,
            "on_set_auto_clear": on_set_auto_clear,
            "on_restore_history_item": on_restore_history_item,
            "on_clear_history": on_clear_history,
        })

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self._badge_visible = False
        self.status_item.button().setImage_(self._make_image(with_badge=False))
        self.status_item.setHighlightMode_(True)

        menu = NSMenu.alloc().init()

        show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Window", "toggleWindow:", ""
        )
        show_item.setTarget_(self.delegate)
        menu.addItem_(show_item)
        self.show_item = show_item

        clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Clear", "clearClipboard:", ""
        )
        clear_item.setTarget_(self.delegate)
        menu.addItem_(clear_item)

        # Auto Clear submenu
        auto_clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Auto Clear", "", ""
        )
        auto_clear_menu = NSMenu.alloc().initWithTitle_("Auto Clear")
        for label, secs in AUTO_CLEAR_INTERVALS:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                label, "setAutoClearInterval:", ""
            )
            item.setTarget_(self.delegate)
            item.setRepresentedObject_(secs)
            item.setState_(NSOnState if secs == 300 else NSOffState)
            auto_clear_menu.addItem_(item)
        auto_clear_item.setSubmenu_(auto_clear_menu)
        menu.addItem_(auto_clear_item)

        # History submenu
        history_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "History", "", ""
        )
        self.history_menu = NSMenu.alloc().initWithTitle_("History")
        self._populate_empty_history_menu()
        history_item.setSubmenu_(self.history_menu)
        menu.addItem_(history_item)

        menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", ""
        )
        quit_item.setTarget_(self.delegate)
        menu.addItem_(quit_item)

        self.status_item.setMenu_(menu)

    def _make_image(self, with_badge=False):
        """Create a status bar image with optional small red badge in the upper-right corner."""
        size = self._ICON_SIZE
        image = NSImage.alloc().initWithSize_((size, size))
        image.lockFocus()

        # Draw the clipboard emoji
        font = NSFont.systemFontOfSize_(size - 4)
        astr = NSAttributedString.alloc().initWithString_attributes_(
            "\U0001f4cb", {NSFontAttributeName: font}
        )
        astr.drawAtPoint_((1, 0))

        if with_badge:
            # Small red circle in upper-right corner, ~25% of icon size
            badge_d = size * 0.28   # ~5px diameter
            badge_x = size - badge_d - 0.5
            badge_y = size - badge_d - 0.5
            # White outline for contrast against any background
            NSColor.whiteColor().setFill()
            NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(badge_x - 1.0, badge_y - 1.0, badge_d + 2.0, badge_d + 2.0)
            ).fill()
            # Red fill
            NSColor.redColor().setFill()
            NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(badge_x, badge_y, badge_d, badge_d)
            ).fill()

        image.unlockFocus()
        return image

    def show_badge(self):
        """Show a small red badge on the menu bar icon."""
        if not self._badge_visible:
            self._badge_visible = True
            self.status_item.button().setImage_(self._make_image(with_badge=True))

    def hide_badge(self):
        """Hide the red badge from the menu bar icon."""
        if self._badge_visible:
            self._badge_visible = False
            self.status_item.button().setImage_(self._make_image(with_badge=False))

    def set_title(self, title):
        self.show_item.setTitle_(title)

    def _populate_empty_history_menu(self):
        empty_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "No History", "", ""
        )
        empty_item.setEnabled_(False)
        self.history_menu.addItem_(empty_item)

    def update_history_menu(self, history):
        """Rebuild the history submenu from the current history list."""
        while self.history_menu.numberOfItems() > 0:
            self.history_menu.removeItemAtIndex_(0)

        if not history:
            self._populate_empty_history_menu()
            return

        for i, item in enumerate(history):
            ts = item["timestamp"].strftime("%H:%M:%S")
            if item["type"] == "text":
                preview = item["data"].replace("\n", " ").replace("\r", "")
                if len(preview) > 50:
                    preview = preview[:50] + "\u2026"
                title = f"{ts}  {preview}"
            else:
                title = f"{ts}  [Image]"

            menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, "restoreHistoryItem:", ""
            )
            menu_item.setTarget_(self.delegate)
            menu_item.setRepresentedObject_(i)
            self.history_menu.addItem_(menu_item)

        self.history_menu.addItem_(NSMenuItem.separatorItem())
        clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Clear History", "clearHistory:", ""
        )
        clear_item.setTarget_(self.delegate)
        self.history_menu.addItem_(clear_item)


class ClipboardWindow(NSObject):
    """Pure AppKit clipboard editor window."""

    def init(self):
        self = objc.super(ClipboardWindow, self).init()
        if self is None:
            return None
        self.pasteboard = NSPasteboard.generalPasteboard()
        self.last_change_count = self.pasteboard.changeCount()
        self.visible = False
        self.menu_bar = None
        self.current_mode = 'text'
        self.current_image = None
        self.updating_from_clipboard = False
        self.timer = None
        self.auto_clear_interval = 300  # default to 5 minutes
        self.auto_clear_timer = None
        self.history = []
        self.window = None
        self._alert_window = None
        self.scroll_view = None
        self.text_view = None
        self.image_view = None
        self.clear_button = None
        self.main_container = None
        self.bottom_bar = None
        return self

    # -- Auto clear --

    def set_auto_clear_interval(self, seconds):
        """Set (or disable) the periodic clipboard auto-clear."""
        if self.auto_clear_timer:
            self.auto_clear_timer.invalidate()
            self.auto_clear_timer = None
        self.auto_clear_interval = seconds
        if seconds > 0:
            self.auto_clear_timer = (
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    seconds, self, "clearClipboard:", None, True
                )
            )

    # -- Window setup --

    def setup_window(self):
        style = (NSTitledWindowMask | NSClosableWindowMask |
                 NSMiniaturizableWindowMask | NSResizableWindowMask)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, 600, 400), style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Hello Clipboard")
        self.window.setDelegate_(self)
        self.window.setMinSize_((300, 200))

    def setup_main_container(self):
        from AppKit import NSView
        frame = self.window.contentView().bounds()
        self.main_container = NSView.alloc().initWithFrame_(frame)
        self.main_container.setAutoresizingMask_(0x12)

        # Bottom bar with Clear button (always visible)
        toolbar_height = 44
        toolbar_frame = NSMakeRect(0, 0, frame.size.width, toolbar_height)
        self.bottom_bar = NSView.alloc().initWithFrame_(toolbar_frame)
        self.bottom_bar.setAutoresizingMask_(0x22)  # flexible width, pin to bottom

        btn_frame = NSMakeRect((frame.size.width - 80) / 2, 8, 80, 28)
        self.clear_button = NSButton.alloc().initWithFrame_(btn_frame)
        self.clear_button.setTitle_("Clear")
        self.clear_button.setBezelStyle_(NSBezelStyleRounded)
        self.clear_button.setTarget_(self)
        self.clear_button.setAction_("clearClipboard:")
        self.clear_button.setAutoresizingMask_(0x05)  # centered horizontally
        self.bottom_bar.addSubview_(self.clear_button)

        self.main_container.addSubview_(self.bottom_bar)
        self.window.setContentView_(self.main_container)

    def setup_text_view(self):
        frame = self.window.contentView().bounds()
        toolbar_height = 44
        content_frame = NSMakeRect(0, toolbar_height, frame.size.width, frame.size.height - toolbar_height)
        self.scroll_view = NSScrollView.alloc().initWithFrame_(content_frame)
        self.scroll_view.setHasVerticalScroller_(True)
        self.scroll_view.setAutoresizingMask_(0x12)  # width + height flexible

        text_frame = NSMakeRect(0, 0, content_frame.size.width, content_frame.size.height)
        self.text_view = NSTextView.alloc().initWithFrame_(text_frame)
        self.text_view.setFont_(NSFont.fontWithName_size_("Monaco", 16))
        self.text_view.setRichText_(False)
        self.text_view.setAutomaticQuoteSubstitutionEnabled_(False)
        self.text_view.setAutomaticDashSubstitutionEnabled_(False)
        self.text_view.setAutomaticTextReplacementEnabled_(False)
        # Allow text view to resize with scroll view
        self.text_view.setMinSize_((0, content_frame.size.height))
        self.text_view.setMaxSize_((1e7, 1e7))
        self.text_view.setVerticallyResizable_(True)
        self.text_view.setHorizontallyResizable_(False)
        self.text_view.textContainer().setWidthTracksTextView_(True)

        self.scroll_view.setDocumentView_(self.text_view)

        # Observe text changes
        self._add_text_observer()

    def _add_text_observer(self):
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "textDidChange:", NSTextDidChangeNotification, self.text_view
        )

    def _remove_text_observer(self):
        NSNotificationCenter.defaultCenter().removeObserver_name_object_(
            self, NSTextDidChangeNotification, self.text_view
        )

    def setup_image_view(self):
        frame = self.window.contentView().bounds()
        toolbar_height = 44
        img_frame = NSMakeRect(0, toolbar_height, frame.size.width, frame.size.height - toolbar_height)
        self.image_view = NSImageView.alloc().initWithFrame_(img_frame)
        self.image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        self.image_view.setAutoresizingMask_(0x12)

    # -- Text change handler --

    @objc.typedSelector(b"v@:@")
    def textDidChange_(self, notification):
        if not self.updating_from_clipboard:
            text = self.text_view.string()
            self.pasteboard.clearContents()
            self.pasteboard.setString_forType_(text, NSPasteboardTypeString)
            self.last_change_count = self.pasteboard.changeCount()
            if self.menu_bar:
                if text:
                    self.menu_bar.show_badge()
                else:
                    self.menu_bar.hide_badge()

    # -- Clipboard I/O --

    def get_clipboard_content(self):
        types = self.pasteboard.types()
        if types is None:
            return ('empty', None)

        for img_type in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            if img_type in types:
                data = self.pasteboard.dataForType_(img_type)
                if data:
                    ns_image = NSImage.alloc().initWithData_(data)
                    if ns_image:
                        return ('image', ns_image)

        if NSPasteboardTypeString in types:
            text = self.pasteboard.stringForType_(NSPasteboardTypeString)
            if text:
                return ('text', text)

        return ('empty', None)

    def _get_raw_image_data(self):
        """Return (img_type, NSData) for the current clipboard image, or None."""
        types = self.pasteboard.types()
        if types is None:
            return None
        for img_type in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            if img_type in types:
                data = self.pasteboard.dataForType_(img_type)
                if data:
                    return (img_type, data)
        return None

    # -- History --

    def add_to_history(self, content_type, data):
        """Prepend an item to history, de-dup against the most recent entry, and trim."""
        if self.history and self.history[0]["type"] == content_type == "text" \
                and self.history[0]["data"] == data:
            return
        self.history.insert(0, {
            "type": content_type,
            "data": data,
            "timestamp": datetime.datetime.now(),
        })
        if len(self.history) > MAX_HISTORY_SIZE:
            self.history = self.history[:MAX_HISTORY_SIZE]
        if self.menu_bar:
            self.menu_bar.update_history_menu(self.history)

    def restore_history_item(self, index):
        """Restore a history entry to the clipboard and update the display."""
        if index < 0 or index >= len(self.history):
            return
        item = self.history[index]
        self.pasteboard.clearContents()
        if item["type"] == "text":
            self.pasteboard.setString_forType_(item["data"], NSPasteboardTypeString)
        else:
            img_type, raw_data = item["data"]
            self.pasteboard.setData_forType_(raw_data, img_type)
        self.last_change_count = self.pasteboard.changeCount()
        content_type, display_data = self.get_clipboard_content()
        if content_type != "empty":
            self.update_window(content_type, display_data)
            if self.menu_bar:
                self.menu_bar.show_badge()

    def clear_history(self):
        """Erase the clipboard history and update the menu."""
        self.history.clear()
        if self.menu_bar:
            self.menu_bar.update_history_menu(self.history)

    # -- Clear clipboard --

    @objc.typedSelector(b"v@:@")
    def clearClipboard_(self, sender):
        self.pasteboard.clearContents()
        self.last_change_count = self.pasteboard.changeCount()
        self.current_image = None
        self.show_text_mode(force=True)
        self.updating_from_clipboard = True
        self.text_view.setString_("")
        self.updating_from_clipboard = False
        if self.menu_bar:
            self.menu_bar.hide_badge()

    # -- Mode switching --

    def _content_frame(self):
        """Current frame for content views: full container minus bottom toolbar."""
        toolbar_height = 44
        b = self.main_container.bounds()
        return NSMakeRect(0, toolbar_height, b.size.width, b.size.height - toolbar_height)

    def show_text_mode(self, force=False):
        if self.current_mode == 'text' and not force:
            return
        self.current_mode = 'text'
        if self.image_view.superview():
            self.image_view.removeFromSuperview()
        if not self.scroll_view.superview():
            self.scroll_view.setFrame_(self._content_frame())
            self.main_container.addSubview_(self.scroll_view)

    def show_image_mode(self):
        if self.current_mode == 'image':
            return
        self.current_mode = 'image'
        if self.scroll_view.superview():
            self.scroll_view.removeFromSuperview()
        if not self.image_view.superview():
            self.image_view.setFrame_(self._content_frame())
            self.main_container.addSubview_(self.image_view)

    # -- Update window from clipboard --

    def update_window(self, content_type, data):
        if content_type == 'text':
            self.show_text_mode()
            self.updating_from_clipboard = True
            self._remove_text_observer()
            self.text_view.setString_(data)
            self._add_text_observer()
            self.updating_from_clipboard = False
        elif content_type == 'image':
            self.show_image_mode()
            self.current_image = data
            self._display_image(data)


    def _display_image(self, ns_image):
        self.image_view.setImage_(ns_image)

    # -- Clipboard polling --

    @objc.typedSelector(b"v@:@")
    def notifySuspiciousDeferred_(self, timer):
        self._notify_suspicious(timer.userInfo())

    def _notify_suspicious(self, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Hello Clipboard detected a potential threat")
        alert.setInformativeText_(
            "Your clipboard contains a command that looks like it could be used to harm your "
            "computer.\n\n"
            "Do not paste this into Terminal or any other app. It\u2019s safe to clear it now."
        )
        alert.addButtonWithTitle_("Clear Clipboard")
        alert.addButtonWithTitle_("Dismiss")
        alert.setAlertStyle_(2)  # NSAlertStyleCritical
        alert.layout()
        # Wire buttons manually so the window is non-modal (menus stay active)
        alert.buttons()[0].setTarget_(self)
        alert.buttons()[0].setAction_("alertClearClipboard:")
        alert.buttons()[1].setTarget_(self)
        alert.buttons()[1].setAction_("alertDismiss:")
        self._alert_window = alert.window()
        self._alert_window.setLevel_(NSFloatingWindowLevel)
        self._alert_window.center()
        self._alert_window.makeKeyAndOrderFront_(None)

    @objc.typedSelector(b"v@:@")
    def alertClearClipboard_(self, sender):
        self._alert_window.close()
        self._alert_window = None
        self.clearClipboard_(None)

    @objc.typedSelector(b"v@:@")
    def alertDismiss_(self, sender):
        self._alert_window.close()
        self._alert_window = None

    @objc.typedSelector(b"v@:@")
    def checkClipboard_(self, timer):
        current_count = self.pasteboard.changeCount()
        if current_count != self.last_change_count:
            self.last_change_count = current_count
            content_type, data = self.get_clipboard_content()
            if content_type != 'empty':
                self.update_window(content_type, data)
                if self.menu_bar:
                    self.menu_bar.show_badge()
                if content_type == 'text':
                    self.add_to_history('text', data)
                elif content_type == 'image':
                    raw = self._get_raw_image_data()
                    if raw:
                        self.add_to_history('image', raw)
            if content_type == 'text' and data:
                warning = check_for_suspicious_content(data)
                if warning:
                    self._notify_suspicious(warning)

    # -- Window delegate --

    def windowShouldClose_(self, sender):
        self.hide()
        return False

    # -- Keyboard handling for image mode --

    @objc.typedSelector(b"v@:@")
    def handleKeyDown_(self, event):
        """Handle Delete/Backspace to clear image."""
        keycode = event.keyCode()
        # 51 = Backspace, 117 = Delete
        if keycode in (51, 117) and self.current_mode == 'image':
            self.clearClipboard_(None)

    # -- Show / Hide / Toggle --

    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        self.window.orderFrontRegardless()
        app = NSApplication.sharedApplication()
        app.activateIgnoringOtherApps_(True)
        self.visible = True
        if self.menu_bar:
            self.menu_bar.set_title("Hide Window")

    def hide(self):
        self.window.orderOut_(None)
        self.visible = False
        if self.menu_bar:
            self.menu_bar.set_title("Show Window")

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def quit_app(self):
        if self.timer:
            self.timer.invalidate()
            self.timer = None
        if self.auto_clear_timer:
            self.auto_clear_timer.invalidate()
            self.auto_clear_timer = None
        NSApplication.sharedApplication().terminate_(None)

    # -- Main menu (Cmd+W support) --

    def setup_main_menu(self):
        """Set up a minimal main menu so Cmd+W hides the window.

        NSApplicationActivationPolicyAccessory apps have no visible menu bar,
        but setting a mainMenu still registers key equivalents.  A Window menu
        with a Close Window item (performClose:, key "w") routes Cmd+W through
        the responder chain to the key window, which calls windowShouldClose_
        (already implemented) and hides the window.
        """
        app = NSApplication.sharedApplication()

        main_menu = NSMenu.alloc().init()

        # macOS requires an application menu as the first item.
        app_menu_item = NSMenuItem.alloc().init()
        main_menu.addItem_(app_menu_item)
        app_menu = NSMenu.alloc().init()
        app_menu_item.setSubmenu_(app_menu)

        # Window menu containing Close Window (Cmd+W).
        window_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Window", "", ""
        )
        main_menu.addItem_(window_menu_item)
        window_menu = NSMenu.alloc().initWithTitle_("Window")
        window_menu_item.setSubmenu_(window_menu)

        close_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Close Window", "performClose:", "w"
        )
        window_menu.addItem_(close_item)

        app.setMainMenu_(main_menu)

    # -- Main entry point --

    def run(self):
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self._app_delegate = AppDelegate.alloc().initWithClipboardWindow_(self)
        app.setDelegate_(self._app_delegate)

        app.run()


class AppDelegate(NSObject):
    """NSApplicationDelegate providing proper macOS app lifecycle management."""

    def initWithClipboardWindow_(self, clipboard_window):
        self = objc.super(AppDelegate, self).init()
        if self is None:
            return None
        self.clipboard_window = clipboard_window
        return self

    def _install_sigint_handler(self):
        """Register SIGINT handler so Ctrl+C from the terminal terminates the app."""
        signal.signal(
            signal.SIGINT,
            lambda s, f: NSApplication.sharedApplication().terminate_(None),
        )

    @objc.typedSelector(b"v@:@")
    def reinstallSigintHandler_(self, timer):
        """Re-register the SIGINT handler periodically (Cocoa run loop may override it)."""
        self._install_sigint_handler()

    def applicationDidFinishLaunching_(self, notification):
        """Set up the window, timer, and menu bar after the app has launched."""
        cw = self.clipboard_window

        cw.setup_window()
        cw.setup_main_menu()
        cw.setup_main_container()
        cw.setup_text_view()
        cw.setup_image_view()

        # Start in text mode
        cw.main_container.addSubview_(cw.scroll_view)

        # Load initial clipboard content
        content_type, data = cw.get_clipboard_content()
        if content_type == 'text' and data:
            cw.updating_from_clipboard = True
            cw._remove_text_observer()
            cw.text_view.setString_(data)
            cw._add_text_observer()
            cw.updating_from_clipboard = False
        elif content_type == 'image' and data:
            cw.update_window('image', data)

        # Menu bar icon
        cw.menu_bar = MenuBarIcon(
            on_toggle=cw.toggle,
            on_quit=cw.quit_app,
            on_clear=cw.clearClipboard_,
            on_set_auto_clear=cw.set_auto_clear_interval,
            on_restore_history_item=cw.restore_history_item,
            on_clear_history=cw.clear_history,
        )

        # Seed history with initial clipboard content (after menu bar exists)
        if content_type == 'text' and data:
            cw.add_to_history('text', data)
        elif content_type == 'image' and data:
            raw = cw._get_raw_image_data()
            if raw:
                cw.add_to_history('image', raw)

        # Check initial clipboard content for suspicious payloads (after menu bar exists)
        if content_type == 'text' and data:
            warning = check_for_suspicious_content(data)
            if warning:
                cw.menu_bar.show_badge()
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    0.0, cw, "notifySuspiciousDeferred:", warning, False
                )

        # Clipboard polling timer
        cw.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, cw, "checkClipboard:", None, True
        )

        # Start auto-clear timer with default interval
        cw.set_auto_clear_interval(cw.auto_clear_interval)

        # SIGINT (Ctrl+C) support: install handler now and re-register every second
        # because Cocoa's run loop replaces Python's default SIGINT handler.
        self._install_sigint_handler()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "reinstallSigintHandler:", None, True
        )

        # Start hidden
        cw.hide()
        if cw.get_clipboard_content()[0] != 'empty':
            cw.menu_bar.show_badge()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_visible_windows):
        """Show the window when the app is reopened (e.g., clicked in Finder or Activity Monitor)."""
        if not has_visible_windows:
            self.clipboard_window.show()
        return True

    def applicationWillTerminate_(self, notification):
        """Invalidate timers on app termination."""
        cw = self.clipboard_window
        if cw.timer:
            cw.timer.invalidate()
            cw.timer = None
        if cw.auto_clear_timer:
            cw.auto_clear_timer.invalidate()
            cw.auto_clear_timer = None


def main():
    window = ClipboardWindow.alloc().init()
    window.run()


if __name__ == "__main__":
    main()
