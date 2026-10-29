"""Connected-device discovery: no name filter, deduplication and failures."""
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import paired_devices as devices

with tempfile.TemporaryDirectory() as directory:
 with patch.object(devices, 'PREFERENCES', Path(directory)/'devices.json'):
  assert devices.load_last_connected() is None
  devices.save_choice('AA')
  assert devices.load_last_connected() is None  # Selection is not a successful connection.
  devices.save_connected('AA')
  devices.save_choice('BB')
  assert devices.load_choice() == 'BB'
  assert devices.load_last_connected() == 'AA'
  devices.PREFERENCES.write_text('{"mac":"LEGACY"}', encoding='utf-8')
  assert devices.load_last_connected() == 'LEGACY'

records = [
 {'Name':'My renamed screen','Address':'aa:bb:cc:dd:ee:ff'},
 {'Name':'Xbox Wireless Controller','Address':'112233445566'},
 {'Name':'Duplicate profile','Address':'AA-BB-CC-DD-EE-FF'},
 {'Name':'Invalid','Address':'not-a-mac'},
]
output='\n'.join(json.dumps(row) for row in records)
assert devices.parse_devices(output)==[
 ('AA:BB:CC:DD:EE:FF','My renamed screen'),
 ('11:22:33:44:55:66','Xbox Wireless Controller')]
with patch('paired_devices.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr='')):
 assert devices.discover()==devices.parse_devices(output)
with patch('paired_devices.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')):
 assert devices.discover()==[]
for error in (subprocess.TimeoutExpired('powershell',40),ValueError('Invalid JSON')):
 with patch('paired_devices.subprocess.run',side_effect=error):
  try: devices.discover()
  except OSError: pass
  else: raise AssertionError('Enumeration failure must reach the UI')
print('Renamed devices, Classic/LE duplicates, empty list and failure handling: OK')
