# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import ssl

datas = [('Get-ConnectedBluetooth.ps1', '.'), ('Get-NowPlaying.ps1', '.'), ('Export-AppIcon.ps1', '.'), ('Update-App.ps1', '.'), ('minitoo.ico', '.')]
binaries = []
hiddenimports = []
datas += collect_data_files('tzdata')
# Some Python distributions ship an additional SSL policy certificate beside ssl.py.
# Preserve it when freezing that distribution; stock Python needs no extra file.
ssl_policy = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if ssl_policy.is_file():
    datas.append((str(ssl_policy), '.'))
tmp_ret = collect_all('zstandard')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['minitoo_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Divoom',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['minitoo.ico'],
)
