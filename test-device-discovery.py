"""Connected-device discovery: no name filter, deduplication and failures."""
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import paired_devices as devices

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
