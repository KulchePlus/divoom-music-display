"""Manual size tests: generate first, send only after an explicit click."""
import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from uuid import uuid4
from PIL import Image, ImageTk
import debug_image
import now_playing as core
from ui_appearance import round_window, round_inputs

BG, PANEL, TEXT, MUTED = '#101318', '#191e26', '#f4f6fa', '#929eaf'


class DebugWindow:
    def __init__(self, app):
        self.app = app
        self.session = uuid4().hex
        self.blob = None
        self.image = None
        self.metadata = None
        self.photo = None
        self.generating = self.sending = self.closed = False
        self.last_result = None
        self.window = tk.Toplevel(app.root)
        round_window(self.window)
        self.window.title('Divoom — Debug')
        self.window.configure(bg=BG)
        self.window.geometry('540x790')
        self.window.minsize(500, 760)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        frame = tk.Frame(self.window, bg=BG)
        frame.pack(fill='both', expand=True, padx=24, pady=22)
        tk.Label(frame, text='Debug', bg=BG, fg=TEXT, font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        tk.Label(frame, text='Один тест — одна отправка', bg=BG, fg=MUTED,
                 font=('Segoe UI', 11)).pack(anchor='w', pady=(0, 14))
        tk.Label(frame, text='Размер загрузки, КБ', bg=BG, fg=TEXT,
                 font=('Segoe UI', 11)).pack(anchor='w')
        self.size = tk.StringVar(value='30')
        self.entry = ttk.Entry(frame, textvariable=self.size, font=('Segoe UI', 14))
        self.entry.pack(fill='x', pady=(6, 8))
        round_inputs(self.window)
        self.size.trace_add('write', self.invalidate)
        self.generate_button = ttk.Button(frame, text='Генерировать', command=self.generate, style='Debug.TButton')
        self.generate_button.pack(fill='x', pady=(0, 12))
        self.canvas = tk.Canvas(frame, width=320, height=256, bg='#080b10', highlightthickness=0)
        self.canvas.pack(pady=(0, 10))
        self.canvas.create_text(160, 128, text='Сначала сгенерируйте картинку', fill=MUTED, font=('Segoe UI', 10))
        self.info = tk.Label(frame, text='JPEG · 160 × 128 · один кадр\n1 КБ = 1024 байта',
                             bg=BG, fg=MUTED, font=('Segoe UI', 10), justify='left', anchor='w')
        self.info.pack(fill='x', pady=(0, 10))
        self.send_button = ttk.Button(frame, text='Отправить', command=self.send, style='Connect.TButton')
        self.send_button.pack(fill='x', pady=(0, 10))
        self.result = tk.Label(frame, text='Обычные обновления остановлены, пока открыто это окно.',
                               bg=BG, fg='#ffd34e', font=('Segoe UI', 10), wraplength=480, justify='left', anchor='w')
        self.result.pack(fill='x', pady=(0, 8))
        observation = tk.Frame(frame, bg=BG)
        observation.pack(fill='x')
        self.yes_button = ttk.Button(observation, text='LOADING был', command=lambda: self.mark(True))
        self.yes_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.no_button = ttk.Button(observation, text='Не было', command=lambda: self.mark(False))
        self.no_button.pack(side='left', fill='x', expand=True, padx=(4, 0))
        tk.Label(frame, text='Точный размер задаётся служебными сегментами JPEG.\nЭто тест объёма передачи, а не сложности декодирования.\nЗакройте Debug, чтобы вернуть обычную карточку.',
                 bg=BG, fg=MUTED, font=('Segoe UI', 9), justify='left', wraplength=480).pack(anchor='w', pady=(12, 0))
        app.controller.set_debug(True)
        app.detail.configure(text='Режим Debug: автоматические отправки приостановлены.')
        app.locale.register_tree(self.window)
        self.update_buttons()
        self.entry.focus_set()

    def invalidate(self, *_):
        if self.generating or self.sending:
            return
        self.blob = None
        self.last_result = None
        self.info.configure(text='Размер изменён. Нажмите «Генерировать».')
        self.update_buttons()

    def update_buttons(self):
        if self.closed:
            return
        busy = self.generating or self.sending
        self.entry.configure(state='disabled' if busy else 'normal')
        self.generate_button.configure(state='disabled' if busy else 'normal')
        ready = self.blob is not None and not busy and self.app.state == 'connected'
        self.send_button.configure(state='normal' if ready else 'disabled')
        self.send_button.configure(text='Отправка…' if self.sending else 'Отправить')
        mark_state = 'normal' if self.last_result and not busy else 'disabled'
        self.yes_button.configure(state=mark_state)
        self.no_button.configure(state=mark_state)

    def generate(self):
        value = self.size.get()
        try:
            debug_image.parse_size(value)
        except ValueError as error:
            self.result.configure(text=str(error), fg='#f48a8a')
            return
        self.generating = True
        self.blob, self.last_result = None, None
        self.result.configure(text='Генерация изображения…', fg='#ffd34e')
        self.update_buttons()

        def work():
            try:
                result = debug_image.generate(value)
                self.app.events.put(('debug_generated', (self.session, result, None)))
            except Exception as error:
                self.app.events.put(('debug_generated', (self.session, None, str(error))))
        threading.Thread(target=work, daemon=True, name='Debug generator').start()

    def send(self):
        if not self.blob or self.sending or self.generating:
            return
        self.sending = True
        self.last_result = None
        self.result.configure(text='Отправляю один кадр. Наблюдайте за экраном MiniToo.', fg='#ffd34e')
        try:
            self.app.controller.send_debug(self.session, self.image, self.blob, self.metadata)
        except Exception as error:
            self.sending = False
            self.result.configure(text=str(error), fg='#f48a8a')
        self.update_buttons()

    def handle_event(self, event, payload):
        if self.closed or payload[0] != self.session:
            return
        if event == 'debug_generated':
            _, result, error = payload
            self.generating = False
            if error:
                self.result.configure(text=error, fg='#f48a8a')
            else:
                self.image, self.blob, self.metadata = result
                self.photo = ImageTk.PhotoImage(self.image.resize((320, 256), Image.Resampling.NEAREST), master=self.window)
                self.canvas.delete('all')
                self.canvas.create_image(160, 128, image=self.photo)
                meta = self.metadata
                self.info.configure(text=f'Загрузка: {meta["payload_bytes"]:,} байт ({meta["payload_bytes"]/1024:g} КБ)\nJPEG: {meta["jpeg_bytes"]:,} байт · 1 кадр · 160 × 128\nС пакетными заголовками: {meta["wire_bytes"]:,} байт')
                self.result.configure(text='Готово. Нажмите «Отправить».' if self.app.state == 'connected'
                                      else 'Готово. Подключитесь к MiniToo в основном окне.', fg='#70d7a3')
        elif event == 'debug_finished':
            self.sending = False
            self.last_result = dict(payload[1], test_id=uuid4().hex,
                                    timestamp=datetime.now().astimezone().isoformat(), loading=None)
            self.write_result(self.last_result)
            self.result.configure(text=f'Приём подтверждён за {payload[1]["duration"]:.3f} с.\nБыла ли на устройстве надпись LOADING?', fg='#70d7a3')
        elif event == 'debug_failed':
            self.sending = False
            self.result.configure(text='Передача не подтверждена: '+payload[1], fg='#f48a8a')
        self.update_buttons()

    def write_result(self, result):
        try:
            with (core.ROOT/'debug-results.jsonl').open('a', encoding='utf-8') as file:
                file.write(json.dumps(result, ensure_ascii=False)+'\n')
        except OSError as error:
            self.result.configure(text='Не удалось сохранить результат: '+str(error), fg='#f48a8a')

    def mark(self, visible):
        if self.last_result:
            self.last_result['loading'] = visible
            self.write_result(self.last_result)
            self.result.configure(text='Записано: LOADING '+('был.' if visible else 'не было.'), fg='#70d7a3')

    def close(self, resume=True):
        if self.closed:
            return
        self.closed = True
        if resume:
            self.app.controller.set_debug(False)
            self.app.detail.configure(text='Возвращаю обычную карточку…' if self.app.controller.desired.is_set()
                                      else 'Предпросмотр работает и без подключения к устройству.')
        self.app.debug_window = None
        self.window.destroy()
