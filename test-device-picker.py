"""Device routing and styling checks without Bluetooth transmissions."""
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from minitoo_app import App

root = tk.Tk()
root.withdraw()
with patch('paired_devices.save_choice') as save:
    app = App(root, start_worker=False)
    app.controller.device_mac = 'AA:AA:AA:AA:AA:AA'
    choices = [('AA:AA:AA:AA:AA:AA', 'Divoom MiniToo'),
               ('BB:BB:BB:BB:BB:BB', 'Divoom MiniToo')]
    app.receive_devices(choices)
    assert app.device_choice.current() == 0
    app.device_choice.current(1)
    app.select_device()
    assert app.controller.device_mac == choices[1][0]
    save.assert_called_with(choices[1][0])
    app.toggle()
    assert app.controller.desired.is_set()
    assert str(app.device_choice.cget('state')) == 'disabled'
    assert str(app.refresh_devices_button.cget('state')) == 'disabled'
    app.toggle()
    app.pump()
    assert str(app.device_choice.cget('state')) == 'readonly'
    app.receive_devices([])
    app.toggle()
    assert not app.controller.desired.is_set()
    app.receive_devices([choices[0]])
    assert app.device_choice.current() == 0
    # Startup reconnects only to the remembered address, once per launch.
    app.startup_device = choices[1][0]
    app.auto_connect_enabled = True
    app.startup_connect_pending = True
    with patch.object(app.controller, 'connect', wraps=app.controller.connect) as connect:
        app.receive_devices(choices)
        assert app.controller.device_mac == choices[1][0]
        connect.assert_called_once()
        app.toggle()
        app.pump()
        app.receive_devices(choices)
        connect.assert_called_once()
    app.startup_connect_pending = True
    with patch.object(app.controller, 'connect') as connect:
        app.receive_devices([choices[0]])
        connect.assert_not_called()
        assert not app.controller.desired.is_set()
    with patch('paired_devices.load_last_connected', return_value=choices[1][0]):
        app.auto_connect_enabled = True
        app.receive_bluetooth_devices(choices)
        assert app.controller.desired.is_set()
        assert app.controller.device_mac == choices[1][0]
        # Unrelated changes do not reconnect; loss followed by arrival does.
        app.receive_bluetooth_devices([choices[0]])
        assert not app.controller.desired.is_set()
        app.pump()
        app.receive_bluetooth_devices(choices)
        assert app.controller.desired.is_set()
        app.toggle()  # Explicit disconnect suppresses further automatic attempts.
        app.pump()
        app.receive_bluetooth_devices([])
        app.receive_bluetooth_devices(choices)
        assert not app.controller.desired.is_set()
    style = ttk.Style(root)
    for name in ('TEntry', 'TCombobox', 'TSpinbox'):
        assert style.lookup(name, 'fieldbackground', ('readonly',)) == '#222a36'
    app.set_language('en', save=False)
    app.receive_devices([])
    assert app.device_var.get() == 'Select a device'
    app.close()
print('Device selection, remembered choice, single-device selection, connection lock and dark inputs: OK')
