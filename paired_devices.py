"""MiniToo devices remembered by Windows."""
import json
import winreg
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

def discover():
    devices = []
    path = r'SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices'
    try:
        parent = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except FileNotFoundError:
        return devices
    with parent:
        for index in range(winreg.QueryInfoKey(parent)[0]):
            key = winreg.EnumKey(parent, index)
            if len(key) != 12 or any(c not in '0123456789abcdefABCDEF' for c in key):
                continue
            try:
                with winreg.OpenKey(parent, key) as child:
                    name = winreg.QueryValueEx(child, 'Name')[0]
                if isinstance(name, bytes):
                    name = name.rstrip(b'\0').decode('utf-8', errors='replace')
                if 'minitoo' not in str(name).lower().replace(' ', '').replace('-', ''):
                    continue
                mac = ':'.join(key[i:i+2] for i in range(0, 12, 2)).upper()
                devices.append((mac, str(name)))
            except OSError:
                continue
    return sorted(devices, key=lambda device: (device[1], device[0]))
