"""Live language switching, unchanged media content and saved preferences."""
import re
import tempfile
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from PIL import Image
import now_playing as core
from minitoo_app import App
import ui_language

root = tk.Tk()
app = App(root, start_worker=False)
app.set_language('ru', save=False)
app.events.put(('preview', ([Image.new('RGB',(160,128))],1000,
                           {'App':'music','Title':'Подключено','Artist':'Исполнитель'})))
app.events.put(('state', ('connected','Подключено')))
app.pump()
app.open_debug()
debug = app.debug_window
debug.size.set('30')
app.set_language('en', save=False)
root.update()
assert app.language_button.cget('text') == 'RU'
assert app.button.cget('text') == 'Disconnect'
assert app.status.cget('text') == '●  Connected'
assert app.track_label.cget('text') == 'Подключено'
assert app.artist_label.cget('text') == 'Исполнитель'
assert debug.generate_button.cget('text') == 'Generate'
assert debug.send_button.cget('text') == 'Send'
assert debug.size.get() == '30'
leftovers = [widget.cget('text') for widget in app.locale.widgets
             if not isinstance(widget._i18n_source, ui_language.Literal)
             and re.search('[А-Яа-яЁё]',str(widget.cget('text')))]
assert not leftovers, leftovers
app.events.put(('state',('disconnected','Отключено')))
app.pump()
assert app.button.cget('text') == 'Connect'
app.set_language('ru', save=False)
assert app.language_button.cget('text') == 'EN'
assert app.button.cget('text') == 'Подключиться'
assert debug.generate_button.cget('text') == 'Генерировать'
with tempfile.TemporaryDirectory(dir=str(Path.cwd()),prefix='language-test-') as folder:
    assert Path(folder).resolve().is_relative_to(Path.cwd().resolve())
    with patch('now_playing.ROOT', Path(folder)):
        app.set_language('en', save=True)
        assert ui_language.load_language() == 'en'
        app.set_language('ru', save=True)
        assert ui_language.load_language() == 'ru'
app.close()
print('RU/EN main window + open Debug + live status, media literals and persistence: OK')
