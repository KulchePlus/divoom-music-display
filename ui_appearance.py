"""Subtle rounded ttk buttons and native Windows window corners."""
import ctypes
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


def _clip_handle(handle, width, height, radius=7):
    gdi = ctypes.WinDLL('gdi32')
    user = ctypes.WinDLL('user32')
    gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int]*6
    gdi.CreateRoundRectRgn.restype = ctypes.c_void_p
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    user.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
    region = gdi.CreateRoundRectRgn(0, 0, width+1, height+1, radius*2, radius*2)
    if region and not user.SetWindowRgn(handle, region, True):
        gdi.DeleteObject(region)


def round_widget(widget, radius=7):
    def apply(event=None):
        if event is not None and event.widget != widget:
            return
        if widget.winfo_exists() and widget.winfo_width() > 1:
            _clip_handle(widget.winfo_id(), widget.winfo_width(), widget.winfo_height(), radius)
    widget.bind('<Configure>', apply, add='+')
    widget.bind('<Map>', apply, add='+')
    widget.after_idle(apply)


def round_inputs(parent):
    for widget in parent.winfo_children():
        if isinstance(widget, (ttk.Entry, ttk.Combobox, ttk.Spinbox)) and not getattr(widget, '_rounded', False):
            widget._rounded = True
            round_widget(widget, 6)
            if isinstance(widget, ttk.Combobox):
                def popup(control=widget):
                    def apply():
                        if not control.winfo_exists():
                            return
                        path = control.tk.call('ttk::combobox::PopdownWindow', str(control))
                        if int(control.tk.call('winfo', 'ismapped', path)):
                            handle = int(str(control.tk.call('winfo', 'id', path)), 0)
                            user = ctypes.WinDLL('user32')
                            user.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                            user.GetAncestor.restype = ctypes.c_void_p
                            handle = user.GetAncestor(handle, 2)
                            _clip_handle(handle, int(control.tk.call('winfo', 'width', path)),
                                         int(control.tk.call('winfo', 'height', path)), 6)
                    control.after(15, apply)
                widget.configure(postcommand=popup)
        round_inputs(widget)


def round_window(window):
    def apply():
        if not window.winfo_exists():
            return
        try:
            user = ctypes.WinDLL('user32', use_last_error=True)
            user.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user.GetAncestor.restype = ctypes.c_void_p
            handle = user.GetAncestor(window.winfo_id(), 2)
            dwm = ctypes.WinDLL('dwmapi')
            dwm.DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                 ctypes.c_void_p, ctypes.c_uint]
            preference = ctypes.c_int(3)  # DWMWCP_ROUNDSMALL
            dwm.DwmSetWindowAttribute(handle, 33, ctypes.byref(preference), 4)
        except (OSError, AttributeError):
            pass
    window.bind('<Map>', lambda event: apply() if event.widget == window else None, add='+')
    window.after_idle(apply)


def rounded_buttons(root, style):
    images = []
    palettes = {
        'TButton': ('#2a3341', '#364356', '#202937', '#202731', '#101318'),
        'Connect.TButton': ('#ffd34e', '#ffe28a', '#d9b13d', '#525760', '#101318'),
        'Debug.TButton': ('#2a3341', '#364356', '#202937', '#202731', '#101318'),
        'Panel.TButton': ('#2a3341', '#364356', '#202937', '#202731', '#191e26'),
        'Language.TButton': ('#202731', '#303c4d', '#19212d', '#191e26', '#101318'),
    }
    for name, (normal, hover, pressed, disabled, background) in palettes.items():
        variants = []
        for color in (normal, hover, pressed, disabled):
            image = Image.new('RGB', (96, 96), background)
            ImageDraw.Draw(image).rounded_rectangle((0, 0, 95, 95), radius=24, fill=color)
            photo = ImageTk.PhotoImage(image.resize((24, 24), Image.Resampling.LANCZOS), master=root)
            images.append(photo)
            variants.append(photo)
        element = 'Rounded'+name
        style.element_create(element, 'image', variants[0],
            ('disabled', variants[3]), ('pressed', variants[2]), ('active', variants[1]),
            border=7, sticky='nsew')
        style.layout(name, [(element, {'sticky': 'nsew', 'children': [
            ('Button.padding', {'sticky': 'nsew', 'children': [
                ('Button.label', {'sticky': 'nsew'})]})]})])
        style.configure(name, foreground='#f4f6fa', background=background)
        style.map(name, foreground=[('disabled', '#929eaf')])
    style.configure('Connect.TButton', foreground='#101318')
    style.configure('Panel.TButton', font=('Segoe UI', 11), padding=(14, 12))
    root._rounded_button_images = images
