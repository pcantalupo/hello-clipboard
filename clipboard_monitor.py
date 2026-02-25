#!/usr/bin/env python3
import objc
import signal
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSClosableWindowMask,
    NSFont,
    NSImage,
    NSImageScaleProportionallyUpOrDown,
    NSImageView,
    NSMenu,
    NSMenuItem,
    NSMiniaturizableWindowMask,
    NSNotificationCenter,
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
    NSWindow,
)
from Foundation import NSMakeRect, NSObject, NSTimer


NSTextDidChangeNotification = "NSTextDidChangeNotification"


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
    """macOS menu bar icon using PyObjC."""

    def __init__(self, on_toggle, on_quit):
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        self.delegate = MenuBarDelegate.alloc().initWithCallbacks_({
            "on_toggle": on_toggle,
            "on_quit": on_quit,
        })

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self.status_item.setTitle_("📋")
        self.status_item.setHighlightMode_(True)

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
        self.window = None
        self.scroll_view = None
        self.text_view = None
        self.image_container = None
        self.image_view = None
        self.clear_button = None
        return self

    # -- Window setup --

    def setup_window(self):
        style = (NSTitledWindowMask | NSClosableWindowMask |
                 NSMiniaturizableWindowMask | NSResizableWindowMask)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, 600, 400), style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("Clipboard Contents")
        self.window.setDelegate_(self)
        self.window.setMinSize_((300, 200))

    def setup_text_view(self):
        frame = self.window.contentView().bounds()
        self.scroll_view = NSScrollView.alloc().initWithFrame_(frame)
        self.scroll_view.setHasVerticalScroller_(True)
        self.scroll_view.setAutoresizingMask_(0x12)  # width + height flexible

        text_frame = NSMakeRect(0, 0, frame.size.width, frame.size.height)
        self.text_view = NSTextView.alloc().initWithFrame_(text_frame)
        self.text_view.setFont_(NSFont.fontWithName_size_("Monaco", 12))
        self.text_view.setRichText_(False)
        self.text_view.setAutomaticQuoteSubstitutionEnabled_(False)
        self.text_view.setAutomaticDashSubstitutionEnabled_(False)
        self.text_view.setAutomaticTextReplacementEnabled_(False)
        # Allow text view to resize with scroll view
        self.text_view.setMinSize_((0, frame.size.height))
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
        from AppKit import NSView
        self.image_container = NSView.alloc().initWithFrame_(frame)
        self.image_container.setAutoresizingMask_(0x12)

        # Image view fills container except bottom 40px for button
        img_frame = NSMakeRect(0, 40, frame.size.width, frame.size.height - 40)
        self.image_view = NSImageView.alloc().initWithFrame_(img_frame)
        self.image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
        self.image_view.setAutoresizingMask_(0x12)
        self.image_container.addSubview_(self.image_view)

        # Clear button at bottom center
        btn_frame = NSMakeRect(
            (frame.size.width - 80) / 2, 8, 80, 28
        )
        self.clear_button = NSButton.alloc().initWithFrame_(btn_frame)
        self.clear_button.setTitle_("Clear")
        self.clear_button.setBezelStyle_(NSBezelStyleRounded)
        self.clear_button.setTarget_(self)
        self.clear_button.setAction_("clearClipboard:")
        # Keep button horizontally centered
        self.clear_button.setAutoresizingMask_(0x04)  # flexible left + right margins
        self.image_container.addSubview_(self.clear_button)

    # -- Text change handler --

    @objc.typedSelector(b"v@:@")
    def textDidChange_(self, notification):
        if not self.updating_from_clipboard:
            text = self.text_view.string()
            self.pasteboard.clearContents()
            self.pasteboard.setString_forType_(text, NSPasteboardTypeString)
            self.last_change_count = self.pasteboard.changeCount()

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

    # -- Clear clipboard --

    @objc.typedSelector(b"v@:@")
    def clearClipboard_(self, sender):
        if self.current_mode != 'image':
            return
        self.pasteboard.clearContents()
        self.last_change_count = self.pasteboard.changeCount()
        self.current_image = None
        self.show_text_mode(force=True)
        self.updating_from_clipboard = True
        self.text_view.setString_("")
        self.updating_from_clipboard = False

    # -- Mode switching --

    def show_text_mode(self, force=False):
        if self.current_mode == 'text' and not force:
            return
        self.current_mode = 'text'
        self.window.setContentView_(self.scroll_view)

    def show_image_mode(self):
        if self.current_mode == 'image':
            return
        self.current_mode = 'image'
        self.window.setContentView_(self.image_container)

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
    def checkClipboard_(self, timer):
        current_count = self.pasteboard.changeCount()
        if current_count != self.last_change_count:
            self.last_change_count = current_count
            content_type, data = self.get_clipboard_content()
            if content_type != 'empty':
                self.update_window(content_type, data)

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
        cw.setup_text_view()
        cw.setup_image_view()

        # Start in text mode
        cw.window.setContentView_(cw.scroll_view)

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
        )

        # Clipboard polling timer
        cw.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, cw, "checkClipboard:", None, True
        )

        # SIGINT (Ctrl+C) support: install handler now and re-register every second
        # because Cocoa's run loop replaces Python's default SIGINT handler.
        self._install_sigint_handler()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "reinstallSigintHandler:", None, True
        )

        # Start hidden
        cw.hide()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_visible_windows):
        """Show the window when the app is reopened (e.g., clicked in Finder or Activity Monitor)."""
        if not has_visible_windows:
            self.clipboard_window.show()
        return True

    def applicationWillTerminate_(self, notification):
        """Invalidate the clipboard polling timer on app termination."""
        cw = self.clipboard_window
        if cw.timer:
            cw.timer.invalidate()
            cw.timer = None


def main():
    window = ClipboardWindow.alloc().init()
    window.run()


if __name__ == "__main__":
    main()
