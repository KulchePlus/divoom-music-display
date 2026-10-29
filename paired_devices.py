"""Connected Bluetooth endpoints reported by Windows."""
import json
import re
import subprocess
import now_playing as core

PREFERENCES = core.ROOT/'device-preferences.json'

def load_preferences():
    try:
        value = json.loads(PREFERENCES.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def load_choice():
    return load_preferences().get('mac')


def load_last_connected():
    preferences = load_preferences()
    # Older versions stored only the chosen device; preserve that setup on upgrade.
    return preferences.get('last_connected_mac', preferences.get('mac'))

def save_choice(mac):
    preferences = load_preferences()
    previous = preferences.get('mac')
    preferences['mac'] = mac
    # Once migrated, changing the selection must not change the reconnect target.
    preferences.setdefault('last_connected_mac', previous)
    save_preferences(preferences)


def save_connected(mac):
    preferences = load_preferences()
    preferences['last_connected_mac'] = mac
    save_preferences(preferences)


def save_preferences(preferences):
    temporary = PREFERENCES.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(preferences), encoding='utf-8')
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
