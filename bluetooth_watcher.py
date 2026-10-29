"""Blocking Windows device events, with no periodic Bluetooth enumeration."""
import json
import logging
import subprocess
import threading
import now_playing as core
import paired_devices


class BluetoothWatcher:
    def __init__(self, events):
        self.events = events
        self.process = None
        self.stopped = threading.Event()
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.run, daemon=True, name='Bluetooth events').start()

    def run(self):
        try:
            with self.lock:
                if self.stopped.is_set():
                    return
                self.process = subprocess.Popen([
                    'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', str(core.RESOURCE_ROOT/'Watch-Bluetooth.ps1')],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding='utf-8-sig', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW)
                process = self.process
            previous = None
            for line in process.stdout:
                if self.stopped.is_set():
                    break
                try:
                    rows = json.loads(line)['Devices']
                    devices = paired_devices.parse_devices('\n'.join(json.dumps(row) for row in rows))
                except (ValueError, KeyError, TypeError):
                    logging.warning('Bluetooth watcher: %s', line.strip())
                    continue
                if devices != previous:
                    self.events.put(('bluetooth_devices', devices))
                    previous = devices
            if not self.stopped.is_set():
                self.events.put(('bluetooth_error', None))
        except OSError:
            logging.exception('Bluetooth event watcher failed')
            if not self.stopped.is_set():
                self.events.put(('bluetooth_error', None))
        finally:
            self.close()

    def close(self):
        self.stopped.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
