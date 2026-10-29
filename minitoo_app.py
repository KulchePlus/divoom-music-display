"""Desktop controller for the MiniToo now-playing display."""
import ctypes
import logging
import queue
import json
import sys
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw
import now_playing as core
from debug_window import DebugWindow
import transmission
import updater
import startup
from version import VERSION
import paired_devices
from ui_language import Localizer, Literal
from ui_tooltip import HelpTip
from ui_appearance import round_window, rounded_buttons, round_widget, round_inputs, switch_style, RoundedGroup

TITLE = f'Divoom — музыкальный экран · v{VERSION}'
BG, PANEL, TEXT, MUTED = '#101318', '#191e26', '#f4f6fa', '#929eaf'


def bug_icon(color):
    scale = 3
    image = Image.new('RGBA', (24*scale, 24*scale))
    draw = ImageDraw.Draw(image)
    def line(points):
        draw.line([(x*scale,y*scale) for x,y in points], fill=color, width=scale, joint='curve')
    for y in (10,14,18):
        line([(8,y),(5,y-1),(4,y-3)])
        line([(16,y),(19,y-1),(20,y-3)])
    line([(10,6),(8,3)])
    line([(14,6),(16,3)])
    draw.ellipse((9*scale,5*scale,15*scale,11*scale), fill=color)
    draw.ellipse((8*scale,8*scale,16*scale,20*scale), fill=color)
    draw.line((12*scale,10*scale,12*scale,19*scale), fill=BG, width=scale)
    return image.resize((24,24), Image.Resampling.LANCZOS)


class Controller:
    """A single worker owns Bluetooth; UI updates only travel through a queue."""
    def __init__(self, events):
        self.events = events
        self.desired = threading.Event()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.display = None
        self.device_mac = paired_devices.load_choice()
        self.debug_mode = threading.Event()
        self.refresh = threading.Event()
        self.manual = queue.Queue(maxsize=1)
        self.settings = transmission.load_settings()
        self.thread = threading.Thread(target=self.run, daemon=True, name='MiniToo worker')

    def connect(self):
        if not self.device_mac:
            raise ValueError('Выберите устройство')
        self.desired.set()
        self.wake.set()

    def disconnect(self):
        self.desired.clear()
        self.wake.set()
        with self.lock:
            if self.display:
                try:
                    self.display.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        self.events.put(('state', ('disconnected', 'Отключено')))

    def close(self):
        self.stop.set()
        self.disconnect()

    def set_debug(self, enabled):
        if enabled:
            self.debug_mode.set()
        else:
            self.debug_mode.clear()
            while True:
                try:
                    self.manual.get_nowait()
                except queue.Empty:
                    break
            self.refresh.set()
        self.wake.set()

    def send_debug(self, session, image, blob, metadata):
        if not self.debug_mode.is_set() or not self.desired.is_set():
            raise RuntimeError('Сначала подключитесь к устройству в основном окне.')
        self.manual.put_nowait((session, image, blob, metadata))
        self.wake.set()

    def set_settings(self, settings):
        with self.lock:
            self.settings = settings
        self.refresh.set()
        self.wake.set()

    def get_settings(self):
        with self.lock:
            return self.settings

    def run(self):
        display, last_sent, key, frames, speed, track = None, None, None, [], 250, {}
        next_scan = 0
        prepared_blob = None
        debug_job = None
        try:
            while not self.stop.is_set():
                try:
                    if self.refresh.is_set():
                        last_sent, key, next_scan = None, None, 0
                        self.refresh.clear()
                    if not self.desired.is_set() and display:
                        display.close()
                        display = None
                        with self.lock:
                            self.display = None
                        self.events.put(('state', ('disconnected', 'Отключено')))
                    if self.desired.is_set() and display is None:
                        self.events.put(('state', ('connecting', 'Подключение к MiniToo…')))
                        display = core.Display(self.device_mac)
                        with self.lock:
                            self.display = display
                        if not self.desired.is_set():
                            continue
                        last_sent = None
                        self.events.put(('state', ('connected', 'Подключено')))
                    if self.debug_mode.is_set():
                        try:
                            debug_job = self.manual.get_nowait()
                        except queue.Empty:
                            debug_job = None
                        if debug_job:
                            session, image, blob, metadata = debug_job
                            if display is None or not self.desired.is_set():
                                raise RuntimeError('Нет соединения с MiniToo.')
                            self.events.put(('state', ('sending', 'Отправка теста…')))
                            self.events.put(('preview', ([image], 1000, {'Title':f'Debug · {len(blob)/1024:g} КБ', 'Artist':'Обычные обновления приостановлены'})))
                            duration = display.send_blob(blob)
                            self.events.put(('debug_finished', (session, dict(metadata, duration=duration))))
                            debug_job, last_sent = None, None
                            if self.desired.is_set():
                                self.events.put(('state', ('connected', 'Подключено')))
                        elif display and self.desired.is_set():
                            list(display.receive(.01))
                        self.wake.wait(.2)
                        self.wake.clear()
                        continue
                    if time.monotonic() >= next_scan:
                        track = core.current_track()
                        settings = self.get_settings()
                        new_key = (track['App'], track['Title'], track['Artist'], track['Status'],
                                   track.get('Cover'), datetime.now(core.ZoneInfo('Europe/Moscow')).strftime('%H:%M'), settings)
                        if new_key != key:
                            original_frames, original_speed = core.animation(track)
                            try:
                                frames, speed, prepared_blob, compression = transmission.prepare(original_frames, original_speed, settings)
                                self.events.put(('compression', compression))
                            except transmission.SizeLimitError as error:
                                frames, speed, prepared_blob = original_frames, original_speed, None
                                self.events.put(('compression_error', str(error)))
                            key = new_key
                            logging.info('Preview prepared: %s frames, %s ms/frame, app=%s', len(frames), speed, track['App'])
                            self.events.put(('preview', (frames, speed, track)))
                        next_scan = time.monotonic()+2
                    if display and self.desired.is_set() and not self.debug_mode.is_set() and not self.refresh.is_set() and prepared_blob and key != last_sent:
                        self.events.put(('state', ('sending', 'Обновление экрана…')))
                        blob = prepared_blob
                        if not self.desired.is_set() or self.debug_mode.is_set():
                            if self.desired.is_set():
                                self.events.put(('state', ('connected', 'Подключено')))
                            continue
                        duration = display.send_blob(blob)
                        if self.desired.is_set():
                            last_sent = key
                            frames[0].save(core.ROOT/'preview.png')
                            self.events.put(('sent', (len(blob), duration, len(frames))))
                            self.events.put(('state', ('connected', 'Подключено')))
                    elif display and self.desired.is_set():
                        # Notice remote disconnection even if the track stays unchanged.
                        list(display.receive(.01))
                    self.wake.wait(.2)
                    self.wake.clear()
                except Exception as error:
                    logging.exception('MiniToo controller error')
                    if debug_job:
                        self.events.put(('debug_failed', (debug_job[0], str(error))))
                        debug_job = None
                    while True:
                        try:
                            pending = self.manual.get_nowait()
                            self.events.put(('debug_failed', (pending[0], str(error))))
                        except queue.Empty:
                            break
                    if display:
                        display.close()
                    display = None
                    with self.lock:
                        self.display = None
                    was_desired = self.desired.is_set()
                    self.desired.clear()
                    message = str(error).strip() or type(error).__name__
                    if was_desired:
                        self.events.put(('state', ('error', 'Не удалось подключиться или обновить экран')))
                        self.events.put(('detail', 'Проверьте, что MiniToo включён и сопряжён с Windows. '+message))
                    else:
                        self.events.put(('state', ('disconnected', 'Отключено')))
                        if not frames:
                            self.events.put(('detail', 'Не удалось прочитать музыку из Windows. '+message))
                    next_scan = time.monotonic()+3
                    self.wake.wait(.5)
                    self.wake.clear()
        finally:
            if display:
                display.close()


class App:
    def __init__(self, root, start_worker=True):
        self.root = root
        self.state = 'disconnected'
        self.events = queue.Queue()
        self.controller = Controller(self.events)
        self.frames, self.frame_ms, self.started = [], 250, time.monotonic()
        self.current_frame = None
        self.photo = None
        self.closed = False
        self.debug_window = None
        self.debug_tip = None
        self.debug_tip_after = None
        self.locale = Localizer()
        self.available_update = None
        self.update_busy = False
        self.auto_check = tk.BooleanVar(master=root, value=updater.load_auto_check(core.ROOT))
        self.start_with_windows = tk.BooleanVar(master=root, value=startup.is_enabled())
        self.startup_check_done = False
        self.devices = []
        self.scanning_devices = False
        root.title(TITLE)
        root.configure(bg=BG)
        root.geometry('680x900')
        root.minsize(620, 840)
        self.tray_icon = None
        root.protocol('WM_DELETE_WINDOW', self.hide_to_tray)
        icon = core.RESOURCE_ROOT/'minitoo.ico'
        if icon.exists():
            root.iconbitmap(str(icon))
        style = ttk.Style(root)
        style.theme_use('clam')
        for input_style in ('TEntry', 'TCombobox', 'TSpinbox'):
            style.configure(input_style, fieldbackground='#222a36', background='#2a3341',
                            foreground=TEXT, insertcolor=TEXT, arrowcolor=MUTED,
                            bordercolor='#394658', lightcolor='#394658', darkcolor='#394658',
                            padding=(10, 8), selectbackground='#495b75', selectforeground=TEXT)
            style.map(input_style, fieldbackground=[('disabled', '#191e26'), ('readonly', '#222a36')],
                      foreground=[('disabled', MUTED), ('readonly', TEXT)],
                      bordercolor=[('focus', '#c6a74e')], lightcolor=[('focus', '#c6a74e')],
                      darkcolor=[('focus', '#c6a74e')])
        root.option_add('*TCombobox*Listbox.background', '#222a36')
        root.option_add('*TCombobox*Listbox.foreground', TEXT)
        root.option_add('*TCombobox*Listbox.selectBackground', '#495b75')
        root.option_add('*TCombobox*Listbox.selectForeground', TEXT)
        root.option_add('*TCombobox*Listbox.font', '{Segoe UI} 11')
        style.configure('Connect.TButton', font=('Segoe UI', 12, 'bold'), padding=(22, 11),
                        foreground='#101318', background='#ffd34e', borderwidth=0)
        style.map('Connect.TButton', background=[('active', '#ffe28a'), ('disabled', '#525760')])
        style.configure('Debug.TButton', font=('Segoe UI', 11), padding=(14, 12),
                        foreground=TEXT, background='#2a3341', borderwidth=0)
        style.configure('Language.TButton', font=('Segoe UI', 10, 'bold'), padding=(9, 4),
                        foreground=MUTED, background='#202731', borderwidth=0)
        rounded_buttons(root, style)
        switch_style(root, style)
        round_window(root)
        outer = tk.Frame(root, bg=BG)
        outer.pack(fill='both', expand=True, padx=28, pady=24)
        header = tk.Frame(outer, bg=BG)
        header.pack(fill='x')
        tk.Label(header, text='Divoom', bg=BG, fg=TEXT, font=('Segoe UI', 25, 'bold')).pack(side='left')
        self.status = tk.Label(header, text='●  Отключено', bg=BG, fg=MUTED, font=('Segoe UI', 11))
        self.status.pack(side='right', pady=(12, 0))
        subtitle_row = tk.Frame(outer, bg=BG)
        subtitle_row.pack(fill='x', pady=(2, 16))
        tk.Label(subtitle_row, text='Музыка с компьютера на вашем экране', bg=BG, fg=MUTED,
                 font=('Segoe UI', 11)).pack(side='left')
        self.language_button = ttk.Button(subtitle_row, text='EN', command=self.toggle_language,
                                          width=3, style='Language.TButton')
        self.language_button.pack(side='right')
        device_row = tk.Frame(outer, bg=BG)
        device_row.pack(fill='x', pady=(0, 14))
        tk.Label(device_row, text='Устройство', bg=BG, fg=MUTED,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 5))
        self.device_var = tk.StringVar()
        self.refresh_devices_button = ttk.Button(device_row, text='Обновить',
            command=self.refresh_devices, style='Language.TButton')
        self.refresh_devices_button.pack(side='right', padx=(10, 0))
        self.device_choice = ttk.Combobox(device_row, textvariable=self.device_var,
            state='readonly', font=('Segoe UI', 10))
        self.device_choice.pack(side='left', fill='x', expand=True)
        self.device_choice.bind('<<ComboboxSelected>>', self.select_device)
        controls = tk.Frame(outer, bg=BG)
        controls.pack(side='bottom', fill='x')
        card = tk.Frame(outer, bg=PANEL, highlightbackground='#2b3340', highlightthickness=1)
        self.preview_card = card
        round_widget(card, 8)
        card.pack(fill='both', expand=True)
        tk.Label(card, text='ПРЕДПРОСМОТР ЭКРАНА', bg=PANEL, fg=MUTED,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=18, pady=(14, 8))
        self.canvas = tk.Canvas(card, width=480, height=256, bg='#080b10', highlightthickness=0)
        self.canvas.pack(padx=18, pady=(0, 10), fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.paint(force=True))
        self.canvas.create_text(240, 192, text='Читаю текущую музыку…', fill=MUTED, tags='placeholder', font=('Segoe UI', 12))
        self.track_label = tk.Label(card, text='Ожидание медиасессии Windows', bg=PANEL, fg=TEXT,
                                    font=('Segoe UI', 11, 'bold'), wraplength=510, justify='left', anchor='w')
        self.track_label.pack(fill='x', padx=18, pady=(0, 4))
        self.artist_label = tk.Label(card, text='', bg=PANEL, fg=MUTED,
                                     font=('Segoe UI', 10), anchor='w', wraplength=510, justify='left')
        self.artist_label.pack(fill='x', padx=18, pady=(0, 12))
        self.transfer_group = RoundedGroup(controls, 'Параметры передачи')
        self.transfer_group.pack(fill='x', pady=(14, 0))
        options = self.transfer_group.content
        for column in range(3):
            options.columnconfigure(column, weight=1)
        initial = self.controller.get_settings()
        self.limit_kb = tk.StringVar(value=f'{initial.budget_bytes/1024:g}')
        self.palette_colors = tk.StringVar(value=str(initial.colors))
        self.max_frames = tk.StringVar(value=str(initial.max_frames))
        self.settings_tips = []
        hints = (
            'Рекомендуемый лимит — 24 КБ. Больше — лучше качество, но дольше загрузка. Лимит действует на каждый кадр; анимация загружается целиком.',
            'Рекомендуем 128 цветов для обложек. Если изображение не укладывается в лимит, попробуйте 64: размер уменьшится, но переходы цветов станут грубее. Для более плавных переходов выберите 256 цветов, если позволяет лимит.',
            'Рекомендуем 1 кадр для быстрой загрузки. Выберите 2, чтобы показывать до четырёх строк названия. Каждый кадр — две строки; больше кадров увеличивает общий объём загрузки.',
        )
        for column, label in enumerate(('Лимит кадра, КБ', 'Количество цветов', 'Максимум кадров')):
            heading = tk.Frame(options, bg=PANEL)
            heading.grid(row=0, column=column, sticky='w', padx=(0, 10))
            tk.Label(heading, text=label, bg=PANEL, fg=TEXT, font=('Segoe UI', 9)).pack(side='left')
            help_button = tk.Label(heading, text='ⓘ', bg=PANEL, fg=MUTED,
                borderwidth=0, highlightthickness=0, font=('Segoe UI', 10),
                cursor='arrow', padx=4, pady=0, takefocus=False)
            help_button.pack(side='left')
            self.settings_tips.append(HelpTip(help_button, hints[column], self.locale))
        ttk.Entry(options, textvariable=self.limit_kb, width=10, font=('Segoe UI', 11)).grid(row=1, column=0, sticky='w', pady=(5, 0))
        options.columnconfigure(1, weight=2, minsize=160)
        self.color_choice = ttk.Combobox(options, textvariable=self.palette_colors,
                                         values=transmission.COLOR_CHOICES, state='readonly',
                                         width=14, height=13, font=('Segoe UI', 12))
        self.color_choice.grid(row=1, column=1, sticky='we', padx=(0, 14), pady=(5, 0))
        ttk.Spinbox(options, from_=1, to=64, textvariable=self.max_frames, width=6,
                    font=('Segoe UI', 11)).grid(row=1, column=2, sticky='w', pady=(5, 0))
        ttk.Button(options, text='Применить', command=self.apply_settings, style='Panel.TButton').grid(row=0, column=3, rowspan=2, padx=(10, 0))
        self.compression_info = tk.Label(options, text='Лимит — на один кадр. Общий объём анимации может быть больше. 1 КБ = 1024 байта.',
                                         bg=PANEL, fg=MUTED, font=('Segoe UI', 9), wraplength=580, justify='left', anchor='w')
        self.compression_info.grid(row=2, column=0, columnspan=4, sticky='we', pady=(9, 0))
        footer = tk.Frame(controls, bg=BG)
        footer.pack(fill='x', pady=(18, 0))
        tk.Label(footer, text='Divoom MiniToo\nBluetooth · 160 × 128', bg=BG, fg=MUTED,
                 font=('Segoe UI', 10), justify='left').pack(side='left')
        self.button = ttk.Button(footer, text='Подключиться', command=self.toggle, style='Connect.TButton')
        self.button.pack(side='right')
        status_row = tk.Frame(controls, bg=BG)
        status_row.pack(fill='x', pady=(12, 0))
        self.detail = tk.Label(status_row, text='Предпросмотр работает и без подключения к устройству.',
                               bg=BG, fg=MUTED, font=('Segoe UI', 9), wraplength=550, justify='left', anchor='w')
        self.detail.pack(side='left', fill='x', expand=True)
        update_row = tk.Frame(controls, bg=BG)
        update_row.pack(fill='x', pady=(10, 0))
        self.auto_update_switch = ttk.Checkbutton(update_row, text='  Автообновления',
            variable=self.auto_check, command=self.save_auto_check, style='Switch.TCheckbutton')
        self.auto_update_switch.pack(side='left')
        self.auto_update_tip = HelpTip(self.auto_update_switch,
            'Проверять новые версии только при запуске приложения. Установка — по кнопке.', self.locale)
        self.update_button = ttk.Button(update_row, text='Проверить обновления',
            command=self.update_action, style='Language.TButton')
        self.update_button.pack(side='right')
        self.startup_switch = ttk.Checkbutton(controls, text='  Запускать при загрузке Windows',
            variable=self.start_with_windows, command=self.save_startup, style='Switch.TCheckbutton')
        self.startup_switch.pack(anchor='w', pady=(7, 0))
        self.update_status = tk.Label(controls, text='', bg=BG, fg=MUTED,
                                      font=('Segoe UI', 9), anchor='w', wraplength=580)
        self.update_status.pack(fill='x', pady=(3, 0))
        self.debug_icon = ImageTk.PhotoImage(bug_icon('#596372'), master=root)
        self.debug_icon_hover = ImageTk.PhotoImage(bug_icon('#929eaf'), master=root)
        self.debug_button = tk.Button(root, image=self.debug_icon, command=self.open_debug,
                                       bg=BG, activebackground=BG, borderwidth=0, highlightthickness=0,
                                       relief='flat', cursor='hand2', padx=2, pady=2, takefocus=True)
        self.debug_button.place(relx=1.0, rely=1.0, anchor='se', x=-2, y=-2)
        self.version_label = tk.Label(root, text=f'v{VERSION}', bg=BG, fg='#596372',
                                      font=('Segoe UI', 9), borderwidth=0, padx=0, pady=0)
        self.version_label.place(relx=1.0, rely=1.0, anchor='se', x=-36, y=-8)
        self.debug_button.bind('<Enter>', self.show_debug_tip)
        self.debug_button.bind('<Leave>', self.hide_debug_tip)
        round_inputs(root)
        self.locale.register_tree(root, skip=(self.language_button,))
        self.language_button.configure(text='EN' if self.locale.language == 'ru' else 'RU')
        if start_worker:
            self.controller.thread.start()
            self.refresh_devices()
            root.after(1500, self.check_updates_at_startup)
        else:
            self.device_placeholder()
        root.after(60, self.pump)

    def save_startup(self):
        try:
            startup.set_enabled(self.start_with_windows.get())
        except OSError:
            logging.exception('Could not save Windows startup setting')
            self.start_with_windows.set(startup.is_enabled())
            self.update_status.configure(text='Не удалось изменить автозапуск Windows.')

    def save_auto_check(self):
        try:
            updater.save_auto_check(core.ROOT, self.auto_check.get())
        except OSError:
            self.auto_check.set(updater.load_auto_check(core.ROOT))
            self.update_status.configure(text='Не удалось сохранить настройку обновлений.')

    def check_updates_at_startup(self):
        if self.startup_check_done or self.closed:
            return
        self.startup_check_done = True
        if self.auto_check.get():
            self.check_updates()

    def update_action(self):
        if self.update_busy:
            return
        if self.available_update:
            if not getattr(sys, 'frozen', False):
                self.update_status.configure(text='Установка доступна в версии EXE.')
                return
            self.update_busy = True
            self.update_button.configure(state='disabled')
            self.update_status.configure(text='Загрузка и проверка SHA-256…')
            release = dict(self.available_update)
            def download():
                try:
                    staging = updater.prepare(release, core.ROOT)
                    updater.launch_install(staging, sys.executable, core.RESOURCE_ROOT)
                    self.events.put(('update_install', None))
                except Exception:
                    logging.exception('Update installation failed')
                    self.events.put(('update_error', 'Не удалось установить обновление. Подробности в логе.'))
            threading.Thread(target=download, daemon=True, name='Divoom update download').start()
        else:
            self.check_updates()

    def check_updates(self):
        if self.closed or self.update_busy:
            return
        self.update_busy = True
        self.update_button.configure(state='disabled')
        self.update_status.configure(text='Проверка обновлений…')
        def check():
            try:
                self.events.put(('update_checked', updater.check()))
            except Exception:
                logging.exception('Update check failed')
                self.events.put(('update_error', 'Проверка недоступна. Попробуйте позже.'))
        threading.Thread(target=check, daemon=True, name='Divoom update check').start()

    def toggle(self):
        if self.state in ('connecting', 'connected', 'sending', 'disconnecting'):
            self.set_state('disconnecting', 'Отключение…')
            self.controller.disconnect()
        else:
            if self.device_choice.current() < 0:
                self.detail.configure(text='Выберите устройство')
                return
            self.detail.configure(text='Соединение с устройством по Bluetooth…')
            self.set_state('connecting', 'Подключение…')
            self.controller.connect()

    def toggle_language(self):
        self.set_language('en' if self.locale.language == 'ru' else 'ru')

    def set_language(self, language, save=True):
        self.hide_debug_tip()
        try:
            self.locale.set_language(language, save=save)
        except OSError as error:
            self.detail.configure(text='Не удалось сохранить язык: '+str(error))
        self.language_button.configure(text='EN' if self.locale.language == 'ru' else 'RU')
        self.device_placeholder()

    def device_placeholder(self):
        if self.device_choice.current() < 0:
            message = 'Поиск устройств…' if self.scanning_devices else 'Выберите устройство'
            self.device_var.set(self.locale.text(message))

    def refresh_devices(self):
        if self.scanning_devices or self.controller.desired.is_set():
            return
        self.scanning_devices = True
        self.refresh_devices_button.configure(state='disabled')
        self.device_choice.configure(state='disabled')
        self.device_placeholder()
        def scan():
            try:
                self.events.put(('devices', paired_devices.discover()))
            except OSError as error:
                self.events.put(('devices_error', str(error)))
        threading.Thread(target=scan, daemon=True, name='MiniToo discovery').start()

    def select_device(self, event=None):
        index = self.device_choice.current()
        if index < 0 or self.controller.desired.is_set():
            return
        self.controller.device_mac = self.devices[index][0]
        try:
            paired_devices.save_choice(self.controller.device_mac)
        except OSError as error:
            self.detail.configure(text='Не удалось сохранить устройство: '+str(error))

    def receive_devices(self, devices):
        self.scanning_devices = False
        self.devices = devices
        self.device_choice.configure(values=[f'{name} · {mac}' for mac, name in devices])
        selected = next((i for i, device in enumerate(devices)
                         if device[0] == self.controller.device_mac), None)
        if selected is None and len(devices) == 1:
            selected = 0
        if selected is not None:
            self.device_choice.current(selected)
            self.select_device()
        else:
            self.device_var.set('')
            self.device_placeholder()
        self.set_state(self.state, self.status._i18n_source.removeprefix('●  '))
        if not devices:
            self.detail.configure(text='Нет подключённых Bluetooth-устройств. Подключите устройство в настройках Windows и нажмите «Обновить».')

    def open_debug(self):
        self.hide_debug_tip()
        if self.debug_window:
            self.debug_window.window.deiconify()
            self.debug_window.window.lift()
            return
        self.debug_window = DebugWindow(self)

    def show_debug_tip(self, event=None):
        self.debug_button.configure(image=self.debug_icon_hover)
        def show():
            self.debug_tip_after = None
            if self.closed:
                return
            self.debug_tip = tk.Toplevel(self.root)
            self.debug_tip.overrideredirect(True)
            self.debug_tip.configure(bg='#303946')
            tk.Label(self.debug_tip, text=self.locale.text('Debug — тестирование передачи'), bg=PANEL, fg=TEXT,
                     font=('Segoe UI', 9), padx=9, pady=5).pack(padx=1, pady=1)
            self.debug_tip.update_idletasks()
            x = self.debug_button.winfo_rootx()+self.debug_button.winfo_width()-self.debug_tip.winfo_reqwidth()
            y = self.debug_button.winfo_rooty()-self.debug_tip.winfo_reqheight()-6
            self.debug_tip.geometry(f'+{max(0,x)}+{max(0,y)}')
        self.hide_debug_tip()
        self.debug_button.configure(image=self.debug_icon_hover)
        self.debug_tip_after = self.root.after(600, show)

    def hide_debug_tip(self, event=None):
        if self.debug_tip_after:
            self.root.after_cancel(self.debug_tip_after)
            self.debug_tip_after = None
        if self.debug_tip:
            self.debug_tip.destroy()
            self.debug_tip = None
        self.debug_button.configure(image=self.debug_icon)

    def apply_settings(self):
        try:
            settings = transmission.Settings.parse(self.limit_kb.get(), self.palette_colors.get(), self.max_frames.get())
            transmission.save_settings(settings)
        except (ValueError, OSError) as error:
            self.compression_info.configure(text=str(error), fg='#f48a8a')
            return
        self.controller.set_settings(settings)
        self.compression_info.configure(text='Настройки сохранены. Пересчитываю размер…', fg='#ffd34e')

    def set_state(self, state, message):
        self.state = state
        color = '#70d7a3' if state in ('connected', 'sending') else '#ffcc66' if state in ('connecting', 'disconnecting') else '#f48a8a' if state == 'error' else MUTED
        self.status.configure(text='●  '+message, fg=color)
        text = 'Отменить' if state == 'connecting' else 'Отключиться' if state in ('connected', 'sending') else 'Отключение…' if state == 'disconnecting' else 'Подключиться'
        self.button.configure(text=text, state='disabled' if state == 'disconnecting' else 'normal')
        busy = state in ('connecting', 'connected', 'sending', 'disconnecting')
        self.device_choice.configure(state='disabled' if busy or self.scanning_devices else 'readonly')
        self.refresh_devices_button.configure(state='disabled' if busy or self.scanning_devices else 'normal')
        if state == 'disconnected':
            self.detail.configure(text='Предпросмотр работает и без подключения к устройству.')
        if self.debug_window:
            self.debug_window.update_buttons()

    def paint(self, force=False):
        if not self.frames or self.closed:
            return
        index = int((time.monotonic()-self.started)*1000/self.frame_ms) % len(self.frames)
        if not force and self.current_frame == index:
            return
        self.current_frame = index
        width, height = max(160, self.canvas.winfo_width()), max(128, self.canvas.winfo_height())
        scale = min(width/160, height/128)
        size = (max(1, int(160*scale)), max(1, int(128*scale)))
        image = self.frames[index].resize(size, Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(image, master=self.root)
        self.canvas.delete('all')
        self.canvas.create_image(width/2, height/2, image=self.photo)

    def pump(self):
        if self.closed:
            return
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == 'tray_show':
                    self.root.deiconify()
                    self.root.lift()
                elif event == 'tray_exit':
                    self.close()
                    return
                elif event == 'state':
                    if self.state != 'disconnecting' or payload[0] in ('disconnected', 'error'):
                        self.set_state(*payload)
                elif event == 'devices':
                    self.receive_devices(payload)
                elif event == 'devices_error':
                    self.receive_devices([])
                    self.detail.configure(text='Не удалось прочитать список устройств: '+payload)
                elif event == 'preview':
                    self.frames, self.frame_ms, track = payload
                    self.started, self.current_frame = time.monotonic(), None
                    title = Literal(track['Title']) if track.get('App') and track['Title'] else track['Title'] or 'Без названия'
                    artist = Literal(track['Artist']) if track.get('App') else track['Artist']
                    self.track_label.configure(text=title)
                    self.artist_label.configure(text=artist)
                    self.paint(force=True)
                elif event == 'detail':
                    self.detail.configure(text=payload)
                elif event == 'sent':
                    size, duration, count = payload
                    self.started = time.monotonic()
                    self.detail.configure(text=f'Экран обновлён · {size/1024:.0f} КБ · {duration:.1f} с · {count} кадр(ов)')
                elif event == 'compression':
                    meta = payload
                    quality = f' · качество {meta["quality"]}' if meta['quality'] else ''
                    warning = f' · только первые {meta["frames"]} кадр(ов) из {meta["original_frames"]}' if meta['reduced'] else ''
                    cadence = f' · {meta["frame_ms"]/1000:g} с/кадр' if meta['frames'] > 1 else ''
                    self.compression_info.configure(text=f'Кадр ≤ {meta["max_frame_bytes"]/1024:.2f} / {meta["budget_bytes"]/1024:g} КБ · вся загрузка {meta["bytes"]/1024:.1f} КБ · {meta["frames"]} кадр(ов) · палитра {meta["colors"]} · {meta["codec"]}{quality}{cadence}{warning}', fg='#70d7a3')
                elif event == 'compression_error':
                    self.compression_info.configure(text=payload, fg='#f48a8a')
                elif event == 'update_checked':
                    self.update_busy = False
                    self.available_update = payload
                    self.update_status.configure(text='Доступна новая версия.' if payload else 'Установлена актуальная версия.')
                    self.update_button.configure(state='normal', text=(
                        f'Установить {payload["tag"]} и перезапустить' if payload else 'Проверить обновления'))
                elif event == 'update_error':
                    self.update_busy = False
                    self.update_status.configure(text=payload)
                    self.update_button.configure(state='normal')
                elif event == 'update_install':
                    self.close()
                    return
                elif event.startswith('debug_') and self.debug_window:
                    self.debug_window.handle_event(event, payload)
        except queue.Empty:
            pass
        self.paint()
        self.root.after(60, self.pump)

    def hide_to_tray(self):
        if self.tray_icon is None:
            try:
                import pystray
                with Image.open(core.RESOURCE_ROOT/'minitoo.ico') as source:
                    icon_image = source.convert('RGBA')
                self.tray_icon = pystray.Icon('Divoom', icon_image, 'Divoom', menu=pystray.Menu(
                    pystray.MenuItem(lambda item: self.locale.text('Открыть'), lambda icon, item: self.events.put(('tray_show', None)), default=True),
                    pystray.MenuItem(lambda item: self.locale.text('Выйти'), lambda icon, item: self.events.put(('tray_exit', None)))))
                self.tray_icon.run_detached()
            except Exception:
                self.tray_icon = None
                logging.exception('Could not create tray icon')
                self.detail.configure(text='Не удалось создать значок в трее.')
                return
        self.hide_debug_tip()
        if self.debug_window:
            self.debug_window.close()
        self.root.withdraw()

    def close(self):
        self.closed = True
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.hide_debug_tip()
        if self.debug_window:
            self.debug_window.close(resume=False)
        self.controller.close()
        self.root.destroy()


def main():
    if '--update-self-test' in sys.argv or '--tls-self-test' in sys.argv:
        report = {'ok': False}
        try:
            import ssl
            context = ssl.create_default_context()
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            result = updater.check() if '--update-self-test' in sys.argv else None
            report = {'ok': True, 'available': result['tag'] if result else None}
        except Exception as error:
            report['error'] = repr(error)
        (core.ROOT/'update-self-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    if '--self-test' in sys.argv:
        report = {'ok': False}
        root = None
        try:
            import ssl
            context = ssl.create_default_context()
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            assert (core.RESOURCE_ROOT/'Get-NowPlaying.ps1').exists()
            assert (core.RESOURCE_ROOT/'Export-AppIcon.ps1').exists()
            assert (core.RESOURCE_ROOT/'Update-App.ps1').exists()
            assert (core.RESOURCE_ROOT/'Get-ConnectedBluetooth.ps1').exists()
            idle_frames, _ = core.animation({'App':'', 'Title':'Нет музыки', 'Artist':'', 'Status':'Stopped'})
            assert len(idle_frames) == 3 and idle_frames[0].size == (160, 128)
            track = core.current_track()
            frames, speed = core.animation(track)
            frames, speed, blob, compression = transmission.prepare(frames, speed, transmission.load_settings())
            root = tk.Tk()
            root.withdraw()
            app = App(root, start_worker=False)
            app.events.put(('preview', (frames, speed, track)))
            app.pump()
            root.update()
            assert app.photo is not None
            import debug_image
            app.open_debug()
            app.debug_window.window.withdraw()
            debug_result = debug_image.generate('30')
            app.debug_window.handle_event('debug_generated', (app.debug_window.session, debug_result, None))
            root.update()
            assert len(app.debug_window.blob) == 30720
            report = {'ok': True, 'frames': len(frames), 'bytes': len(blob),
                      'media_app': track['App'], 'tk': root.tk.call('info', 'patchlevel'),
                      'debug_bytes': len(app.debug_window.blob), 'compression': compression}
        except Exception as error:
            report['error'] = repr(error)
        finally:
            if root:
                root.destroy()
            (core.ROOT/'app-self-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, 'Local\\DivoomMiniTooNowPlaying')
    if ctypes.get_last_error() == 183:
        user = ctypes.windll.user32
        handle = user.FindWindowW(None, TITLE) or user.FindWindowW(None, f'Divoom — music display · v{VERSION}')
        if handle:
            user.ShowWindow(handle, 9)
            user.SetForegroundWindow(handle)
        else:
            language = Localizer()
            user.MessageBoxW(None, language.text('Divoom уже используется фоновой программой. Остановите её через Stop.cmd.'), language.text(TITLE), 0x40)
        return
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.FileHandler(core.ROOT/'now-playing.log', encoding='utf-8')])
    root = tk.Tk()
    app = App(root)
    if '--background' in sys.argv:
        app.hide_to_tray()
    root.mainloop()


if __name__ == '__main__':
    main()
