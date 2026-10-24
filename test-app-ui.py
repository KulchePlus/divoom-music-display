"""UI smoke check without Bluetooth or changing playback."""
import tkinter as tk
import time
from PIL import Image
from minitoo_app import App
from unittest.mock import patch

root = tk.Tk()
app = App(root, start_worker=False)
with patch('paired_devices.save_choice'):
    app.receive_devices([('00:11:22:33:44:55', 'Divoom MiniToo')])
root.update()
assert app.state == 'disconnected'
assert app.button.cget('text') == 'Подключиться'
app.toggle()
assert app.controller.desired.is_set() and app.state == 'connecting'
app.toggle()
app.pump()
assert not app.controller.desired.is_set() and app.state == 'disconnected'
frame = Image.new('RGB', (160, 128), '#123456')
app.events.put(('preview', ([frame, frame.copy()], 250, {'Title':'Тестовый трек','Artist':'Исполнитель'})))
app.events.put(('state', ('connected', 'Подключено')))
app.pump()
root.update()
assert app.photo is not None and app.track_label.cget('text') == 'Тестовый трек'
assert app.button.cget('text') == 'Отключиться'
app.events.put(('state', ('error', 'Ошибка подключения')))
app.pump()
assert app.button.cget('text') == 'Подключиться'
assert app.button.winfo_y()+app.button.winfo_height() <= app.button.master.winfo_height()+1
app.open_debug()
debug = app.debug_window
assert app.controller.debug_mode.is_set()
debug.size.set('0')
debug.generate()
assert debug.blob is None
debug.size.set('30')
debug.generate()
deadline = time.monotonic()+5
while debug.generating and time.monotonic() < deadline:
    root.update()
    app.pump()
    time.sleep(.01)
assert len(debug.blob) == 30720
assert str(debug.send_button.cget('state')) == 'disabled'
app.set_state('connected', 'Подключено')
app.controller.desired.set()
debug.send()
job = app.controller.manual.get_nowait()
assert job[0] == debug.session and len(job[2]) == 30720
debug.write_result = lambda result: None
debug.handle_event('debug_finished', (debug.session, dict(debug.metadata, duration=.3)))
debug.mark(False)
assert debug.last_result['loading'] is False
debug.close()
assert not app.controller.debug_mode.is_set() and app.controller.refresh.is_set()
app.controller.desired.clear()
app.close()
print('UI smoke check: connection, preview, Debug validation/generation/manual send/result/restore and close OK')
