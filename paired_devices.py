"""Connected Bluetooth endpoints reported by Windows."""
import json
import re
import subprocess
import now_playing as core

PREFERENCES = core.ROOT/'device-preferences.json'

def load_choice():
    try:
        return json.loads(PREFERENCES.read_text(encoding='utf-8-sig')).get('mac')
    except (OSError, ValueError, TypeError):
        return None

def save_choice(mac):
    temporary = PREFERENCES.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'mac': mac}), encoding='utf-8')
    temporary.replace(PREFERENCES)

def parse_devices(output):
    devices = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        address = str(item.get('Address', '')).replace(':', '').replace('-', '')
        if not re.fullmatch(r'[0-9a-fA-F]{12}', address):
            continue
        mac = ':'.join(address[i:i+2] for i in range(0, 12, 2)).upper()
        name = str(item.get('Name') or 'Bluetooth').strip() or 'Bluetooth'
        devices.setdefault(mac, name)
    return sorted(devices.items(), key=lambda device: (device[1].casefold(), device[0]))


def discover():
    """Connected Classic and LE endpoints; never probe or connect to devices."""
    try:
        result = subprocess.run([
            'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', str(core.RESOURCE_ROOT/'Get-ConnectedBluetooth.ps1')
        ], capture_output=True, encoding='utf-8-sig', errors='replace', timeout=40,
           creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise OSError(result.stderr.strip() or 'Windows Bluetooth enumeration failed')
        return parse_devices(result.stdout)
    except (subprocess.SubprocessError, ValueError, TypeError) as error:
        raise OSError('Windows Bluetooth enumeration failed: '+str(error)) from error
