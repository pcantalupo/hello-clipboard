#!/usr/bin/env python3
import tkinter as tk
import subprocess
import time

class ClipboardMonitor:
    def __init__(self):
        self.last_content = ""
        self.monitoring = True
        self.root = None
        self.text_widget = None
        self.updating_from_clipboard = False  # Prevent feedback loop
        
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
            
            # Bring window to front
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after_idle(self.root.attributes, '-topmost', False)
    
    def on_text_change(self, event=None):
        """Called when user edits the text widget"""
        if not self.updating_from_clipboard:
            # Get current text from widget
            current_text = self.text_widget.get('1.0', 'end-1c')
            
            # Update system clipboard
            self.set_clipboard_text(current_text)
            self.last_content = current_text
    
    def check_clipboard(self):
        """Periodically check clipboard and update window"""
        current = self.get_clipboard_text()
        
        # Only update if clipboard changed externally
        if current != self.last_content and current.strip():
            self.last_content = current
            self.update_window(current)
        
        # Schedule next check
        if self.monitoring:
            self.root.after(500, self.check_clipboard)
    
    def start(self):
        # Create main window
        self.root = tk.Tk()
        self.root.title("Clipboard Contents")
        self.root.geometry("600x400")
        
        # Text widget with scrollbar (editable)
        self.text_widget = tk.Text(self.root, wrap=tk.WORD, font=("Monaco", 12))
        scrollbar = tk.Scrollbar(self.root, command=self.text_widget.yview)
        self.text_widget.config(yscrollcommand=scrollbar.set)
        
        # Show initial clipboard content
        initial_content = self.get_clipboard_text()
        if initial_content:
            self.last_content = initial_content
            self.text_widget.insert('1.0', initial_content)
        
        # Bind text changes to update clipboard
        self.text_widget.bind('<<Modified>>', self.on_text_modified)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Start checking clipboard
        self.root.after(500, self.check_clipboard)
        
        # Run main loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nStopped monitoring")
            self.monitoring = False
    
    def on_text_modified(self, event=None):
        """Handle text modification events"""
        if self.text_widget.edit_modified():
            self.on_text_change()
            self.text_widget.edit_modified(False)

if __name__ == "__main__":
    monitor = ClipboardMonitor()
    monitor.start()
