"""Event stream deduplication, failure fallback and process cleanup."""
import io
import json
import queue
from unittest.mock import Mock, patch
from bluetooth_watcher import BluetoothWatcher

record = json.dumps({'Devices': [{'Name': 'Renamed display', 'Address': 'AABBCCDDEEFF'}]})
process = Mock(stdout=io.StringIO(record+'\n'+record+'\n'+json.dumps({'Devices': []})+'\n'))
process.poll.return_value = None
events = queue.Queue()
with patch('bluetooth_watcher.subprocess.Popen', return_value=process):
    watcher = BluetoothWatcher(events)
    watcher.run()
assert events.get_nowait() == ('bluetooth_devices', [('AA:BB:CC:DD:EE:FF', 'Renamed display')])
assert events.get_nowait() == ('bluetooth_devices', [])
assert events.get_nowait() == ('bluetooth_error', None)
assert events.empty()
process.terminate.assert_called_once()
process.wait.assert_called_once()
with patch('bluetooth_watcher.subprocess.Popen') as launch:
    watcher = BluetoothWatcher(events)
    watcher.close()
    watcher.run()
    launch.assert_not_called()
print('Bluetooth events: snapshots, deduplication, failure fallback and shutdown: OK')
