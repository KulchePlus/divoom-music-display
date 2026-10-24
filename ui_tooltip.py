"""Small accessible help popovers for settings."""
import tkinter as tk


class HelpTip:
    def __init__(self, widget, text, locale):
        self.widget, self.text, self.locale = widget, text, locale
        self.window = None
        self.pending = None
        widget.bind('<Enter>', self.schedule)
        widget.bind('<Leave>', self.hide)
        widget.bind('<Escape>', self.hide)
        widget.bind('<Destroy>', self.hide)

    def schedule(self, event=None):
        self.hide()
        self.pending = self.widget.after(350, self.show)

    def show(self, event=None):
        self.hide()
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.configure(bg='#394658')
        tk.Label(self.window, text=self.text, bg='#222a36', fg='#f4f6fa',
                 font=('Segoe UI', 10), wraplength=290, justify='left',
                 padx=13, pady=11).pack(padx=1, pady=1)
        self.locale.register_tree(self.window)
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = min(self.widget.winfo_rootx(), self.widget.winfo_screenwidth()-width-8)
        y = self.widget.winfo_rooty()+self.widget.winfo_height()+7
        if y+height > self.widget.winfo_screenheight()-8:
            y = self.widget.winfo_rooty()-height-7
        self.window.geometry(f'+{max(8, x)}+{max(8, y)}')

    def hide(self, event=None):
        if self.pending:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.window:
            self.window.destroy()
            self.window = None
