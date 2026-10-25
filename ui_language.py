"""Live RU/EN text bindings; playback content is kept verbatim."""
import json
import tkinter as tk
import now_playing as core


class Literal(str):
    """A song title or artist name that must never be translated."""


TRANSLATIONS = {
    ' кадр(ов) из ': ' frame(s) of ',
    'Автообновления': 'Auto updates',
    'Проверять новые версии только при запуске приложения. Установка — по кнопке.': 'Check for new versions only when the app starts. Installation requires a button click.',
    'Не удалось сохранить настройку обновлений.': 'Could not save the update preference.',
    'Проверить обновления': 'Check for updates',
    'Проверка обновлений…': 'Checking for updates…',
    'Установлена актуальная версия.': 'You are up to date.',
    'Доступна новая версия.': 'A new version is available.',
    'Установить ': 'Install ', ' и перезапустить': ' and restart',
    'Загрузка и проверка SHA-256…': 'Downloading and verifying SHA-256…',
    'Установка доступна в версии EXE.': 'Installation is available in the EXE build.',
    'Проверка недоступна. Попробуйте позже.': 'Update check unavailable. Try again later.',
    'Не удалось установить обновление. Подробности в логе.': 'Could not install the update. See the log for details.',
    'Устройство': 'Device', 'Обновить': 'Refresh',
    'Выберите устройство': 'Select a device', 'Поиск устройств…': 'Finding devices…',
    'Не удалось сохранить устройство: ': 'Could not save the device: ',
    'Не удалось прочитать список устройств: ': 'Could not read the device list: ',
    'Нет подключённых Bluetooth-устройств. Подключите устройство в настройках Windows и нажмите «Обновить».': 'No Bluetooth devices are connected. Connect a device in Windows settings, then click Refresh.',
    'Divoom — музыкальный экран': 'Divoom — music display',
    'Divoom уже используется фоновой программой. Остановите её через Stop.cmd.': 'Divoom is already in use by the background program. Stop it with Stop.cmd.',
    'Музыка с компьютера на вашем экране': 'Music from your computer, on your display',
    'ПРЕДПРОСМОТР ЭКРАНА': 'DISPLAY PREVIEW',
    'Читаю текущую музыку…': 'Reading current playback…',
    'Ожидание медиасессии Windows': 'Waiting for Windows media playback',
    'Параметры передачи': 'Transfer settings',
    'Лимит кадра, КБ': 'Per-frame limit, KB',
    'Рекомендуемый лимит — 24 КБ. Больше — лучше качество, но дольше загрузка. Лимит действует на каждый кадр; анимация загружается целиком.': 'Recommended limit: 24 KB. Larger images allow better quality but take longer to upload. The limit applies to each frame; animations upload as a whole.',
    'Рекомендуем 128 цветов для обложек. Если изображение не укладывается в лимит, попробуйте 64: размер уменьшится, но переходы цветов станут грубее. Для более плавных переходов выберите 256 цветов, если позволяет лимит.': 'Use 128 colors for album art. If the image exceeds the limit, try 64: this reduces size but makes color transitions less smooth. Choose 256 colors for smoother transitions if the size limit allows.',
    'Рекомендуем 1 кадр для быстрой загрузки. Выберите 2, чтобы показывать до четырёх строк названия. Каждый кадр — две строки; больше кадров увеличивает общий объём загрузки.': 'Use 1 frame for a quick upload. Choose 2 to display up to four title lines. Each frame holds two lines; more frames increase the total upload size.',
    'Количество цветов': 'Color count',
    'Максимум кадров': 'Maximum frames',
    'Применить': 'Apply',
    'Лимит — на один кадр. Общий объём анимации может быть больше. 1 КБ = 1024 байта.': 'The limit applies to each frame. The full animation may be larger. 1 KB = 1024 bytes.',
    'Подключиться': 'Connect', 'Отключиться': 'Disconnect', 'Отменить': 'Cancel',
    'Подключение к MiniToo…': 'Connecting to MiniToo…',
    'Соединение с устройством по Bluetooth…': 'Connecting over Bluetooth…',
    'Подключение…': 'Connecting…', 'Отключение…': 'Disconnecting…',
    'Отключено': 'Disconnected', 'Подключено': 'Connected',
    'Обновление экрана…': 'Updating display…', 'Отправка теста…': 'Sending test…',
    'Предпросмотр работает и без подключения к устройству.': 'The preview also works while disconnected.',
    'Debug — тестирование передачи': 'Debug — transfer tests',
    'Режим Debug: автоматические отправки приостановлены.': 'Debug mode: automatic transfers are paused.',
    'Настройки сохранены. Пересчитываю размер…': 'Settings saved. Recalculating size…',
    'Не удалось подключиться или обновить экран': 'Connection or display update failed',
    'Проверьте, что MiniToo включён и сопряжён с Windows. ': 'Check that MiniToo is powered on and paired with Windows. ',
    'Не удалось прочитать музыку из Windows. ': 'Could not read Windows playback information. ',
    'Сначала подключитесь к устройству в основном окне.': 'Connect to the device in the main window first.',
    'Нет соединения с MiniToo.': 'MiniToo is not connected.',
    'Обычные обновления приостановлены': 'Automatic updates are paused',
    'Без названия': 'Untitled', 'Нет музыки': 'No music',
    'Один тест — одна отправка': 'One test — one transfer',
    'Размер загрузки, КБ': 'Upload size, KB',
    'Генерировать': 'Generate', 'Отправить': 'Send', 'Отправка…': 'Sending…',
    'Сначала сгенерируйте картинку': 'Generate an image first',
    'JPEG · 160 × 128 · один кадр\n1 КБ = 1024 байта': 'JPEG · 160 × 128 · one frame\n1 KB = 1024 bytes',
    'Обычные обновления остановлены, пока открыто это окно.': 'Automatic updates are paused while this window is open.',
    'LOADING был': 'LOADING appeared', 'Не было': 'Did not appear',
    'Точный размер задаётся служебными сегментами JPEG.\nЭто тест объёма передачи, а не сложности декодирования.\nЗакройте Debug, чтобы вернуть обычную карточку.': 'JPEG metadata is used to reach the exact size.\nThis tests transfer size, not decoding complexity.\nClose Debug to restore the music card.',
    'Размер изменён. Нажмите «Генерировать».': 'Size changed. Click Generate.',
    'Генерация изображения…': 'Generating image…',
    'Отправляю один кадр. Наблюдайте за экраном MiniToo.': 'Sending one frame. Watch the MiniToo display.',
    'Готово. Нажмите «Отправить».': 'Ready. Click Send.',
    'Готово. Подключитесь к MiniToo в основном окне.': 'Ready. Connect to MiniToo in the main window.',
    'Передача не подтверждена: ': 'Transfer was not acknowledged: ',
    'Не удалось сохранить результат: ': 'Could not save the result: ',
    'Записано: LOADING был.': 'Saved: LOADING appeared.',
    'Записано: LOADING не было.': 'Saved: LOADING did not appear.',
    'Возвращаю обычную карточку…': 'Restoring the music card…',
    'Введите число от 1 до 1024 КБ.': 'Enter a number from 1 to 1024 KB.',
    'Допустимый размер: от 1 до 1024 КБ.': 'Allowed size: 1 to 1024 KB.',
    'Не удалось подготовить JPEG заданного размера.': 'Could not create a JPEG of the requested size.',
    'Максимум кадров должен быть целым числом от 1 до 64.': 'Maximum frames must be an integer from 1 to 64.',
    'Выберите палитру от 8 до 256 цветов из списка.': 'Choose a color count from the list (8–256).',
    'Максимум кадров: от 1 до 64.': 'Maximum frames: 1 to 64.',
    'Ожидаются кадры 160 × 128.': 'Expected 160 × 128 frames.',
    'Не удалось сохранить язык: ': 'Could not save the language: ',
    'Не удалось сжать каждый кадр до ': 'Could not compress each frame below ',
    ' КБ: требуется не менее ': ' KB: at least ',
    ' КБ на кадр. Увеличьте лимит. На устройство ничего не отправлено.': ' KB per frame is required. Increase the limit. Nothing was sent.',
    'Приём подтверждён за ': 'Transfer acknowledged in ',
    ' с.\nБыла ли на устройстве надпись LOADING?': ' s.\nDid LOADING appear on the device?',
    'Загрузка: ': 'Upload: ', 'С пакетными заголовками: ': 'Including packet headers: ',
    'Обновление экрана': 'Display update', 'Экран обновлён': 'Display updated',
    'Кадр ≤ ': 'Frame ≤ ', 'вся загрузка ': 'total upload ',
    'только первые ': 'first ', ' стр. из ': ' pages of ',
    'кадр(ов)': 'frame(s)', '1 кадр': '1 frame', 'качество ': 'quality ',
    'палитра ': 'colors ', 'с/кадр': 's/frame', ' с · ': ' s · ', 'КБ': 'KB', 'байт': 'bytes',
}
REPLACEMENTS = sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True)


def load_language():
    try:
        value = json.loads((core.ROOT/'ui-preferences.json').read_text(encoding='utf-8'))['language']
        return value if value in ('ru', 'en') else 'ru'
    except (OSError, ValueError, KeyError, TypeError):
        return 'ru'


class Localizer:
    def __init__(self):
        self.language = load_language()
        self.widgets = []
        self.windows = []
        self.canvases = []

    def text(self, source):
        if self.language == 'ru' or isinstance(source, Literal):
            return str(source)
        text = str(source)
        for russian, english in REPLACEMENTS:
            text = text.replace(russian, english)
        return text

    def register_tree(self, widget, skip=()):
        if widget in skip:
            return
        if isinstance(widget, (tk.Tk, tk.Toplevel)) and not getattr(widget, '_i18n_window', False):
            widget._i18n_window = True
            self.windows.append((widget, widget.title()))
        if 'text' in widget.keys() and not getattr(widget, '_i18n_bound', False):
            widget._i18n_bound = True
            widget._i18n_source = widget.cget('text')
            original = widget.configure
            widget._i18n_configure = original
            def configure(cnf=None, _widget=widget, _original=original, **kwargs):
                options = dict(cnf) if isinstance(cnf, dict) else {}
                options.update(kwargs)
                if 'text' in options:
                    _widget._i18n_source = options['text']
                    options['text'] = self.text(options['text'])
                if isinstance(cnf, dict):
                    return _original(options)
                return _original(cnf, **options)
            widget.configure = widget.config = configure
            self.widgets.append(widget)
        if isinstance(widget, tk.Canvas):
            for item in widget.find_all():
                if widget.type(item) == 'text' and (widget, item) not in [(w,i) for w,i,_ in self.canvases]:
                    self.canvases.append((widget, item, widget.itemcget(item, 'text')))
        for child in widget.winfo_children():
            self.register_tree(child, skip)
        self.apply()

    def apply(self):
        self.widgets = [widget for widget in self.widgets if widget.winfo_exists()]
        for widget in self.widgets:
            widget._i18n_configure(text=self.text(widget._i18n_source))
        self.windows = [(window, source) for window, source in self.windows if window.winfo_exists()]
        for window, source in self.windows:
            window.title(self.text(source))
        for canvas, item, source in self.canvases:
            if canvas.winfo_exists() and canvas.type(item) == 'text':
                canvas.itemconfigure(item, text=self.text(source))

    def set_language(self, language, save=True):
        if language not in ('ru', 'en'):
            raise ValueError(language)
        self.language = language
        self.apply()
        if save:
            path = core.ROOT/'ui-preferences.json'
            temporary = path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps({'language':language}), encoding='utf-8')
            temporary.replace(path)
