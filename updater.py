"""Public GitHub Releases updates; no account or token required."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from version import VERSION

REPOSITORY = 'KulchePlus/divoom-music-display'
API = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_DOWNLOAD = 100 * 1024 * 1024


def load_auto_check(directory):
    try:
        value = json.loads((Path(directory)/'update-preferences.json').read_text(encoding='utf-8'))['auto_check']
        return value if isinstance(value, bool) else True
    except (OSError, ValueError, KeyError, TypeError):
        return True


def save_auto_check(directory, enabled):
    path = Path(directory)/'update-preferences.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'auto_check': bool(enabled)}), encoding='utf-8')
    temporary.replace(path)


def version(value):
    match = re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value)
    if not match:
        raise ValueError('Unsupported release version')
    return tuple(map(int, match.groups()))


def read_url(url, limit):
    if not url.startswith('https://'):
        raise ValueError('HTTPS is required')
    request = urllib.request.Request(url, headers={
        'User-Agent': f'Divoom-Music-Display/{VERSION}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Insecure redirect')
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Download exceeds size limit')
    return data


def parse_release(data, current=VERSION):
    if data.get('draft') or data.get('prerelease'):
        return None
    tag = data['tag_name']
    if version(tag) <= version(current):
        return None
    assets = {asset['name']: asset for asset in data.get('assets', [])}
    name = 'Divoom.zip' if 'Divoom.zip' in assets else f'Divoom-{tag}-windows-x64.zip'
    if name not in assets or 'SHA256SUMS.txt' not in assets:
        raise ValueError('Release assets are incomplete')
    prefix = f'https://github.com/{REPOSITORY}/releases/download/{tag}/'
    for filename in (name, 'SHA256SUMS.txt'):
        if assets[filename]['browser_download_url'] != prefix+filename:
            raise ValueError('Unexpected release asset URL')
    return {'tag': tag, 'name': name, 'zip_url': prefix+name,
            'checksum_url': prefix+'SHA256SUMS.txt'}


def check():
    return parse_release(json.loads(read_url(API, 512*1024)))


def prepare(release, directory):
    """Stage only the EXE; never extract settings or paths from the ZIP."""
    checksums = read_url(release['checksum_url'], 64*1024).decode('ascii')
    matches = []
    for line in checksums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == release['name']:
            if re.fullmatch(r'[a-fA-F0-9]{64}', parts[0]):
                matches.append(parts[0].lower())
    if len(matches) != 1:
        raise ValueError('Release checksum is missing or ambiguous')
    archive = read_url(release['zip_url'], MAX_DOWNLOAD)
    if hashlib.sha256(archive).hexdigest() != matches[0]:
        raise ValueError('SHA-256 verification failed')
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = [entry for entry in bundle.infolist() if entry.filename == 'Divoom.exe']
        if len(entries) != 1 or not 2 <= entries[0].file_size <= MAX_DOWNLOAD:
            raise ValueError('Release must contain exactly one Divoom.exe')
        executable = bundle.read(entries[0])
    if not executable.startswith(b'MZ'):
        raise ValueError('Invalid Windows executable')
    staging = Path(tempfile.mkdtemp(prefix='.divoom-update-', dir=directory))
    try:
        (staging/'Divoom.exe').write_bytes(executable)
        return staging
    except BaseException:
        shutil.rmtree(staging)
        raise


def launch_install(staging, target, resource_root):
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Installation is only available in the packaged EXE')
    target = Path(target).resolve()
    staging = Path(staging).resolve()
    if target.name != 'Divoom.exe' or staging.parent != target.parent:
        raise ValueError('Unexpected installation path')
    helper = staging/'Update-App.ps1'
    shutil.copy2(Path(resource_root)/'Update-App.ps1', helper)
    process = subprocess.Popen([
        'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(helper), '-AppProcessId', str(os.getpid()),
        '-Target', str(target), '-Staging', str(staging),
    ], creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(100):
        if (staging/'ready').exists():
            return process
        if process.poll() is not None:
            raise RuntimeError('Update helper failed to start')
        time.sleep(.05)
    process.terminate()
    raise TimeoutError('Update helper did not become ready')
