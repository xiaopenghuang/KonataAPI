# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['ttkbootstrap', 'ttkbootstrap.themes', 'ttkbootstrap.style', 'ttkbootstrap.widgets', 'ttkbootstrap.widgets.scrolled', 'ttkbootstrap.constants', 'ttkbootstrap.window', 'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk', 'requests', 'pystray', 'pystray._win32']
hiddenimports += collect_submodules('ttkbootstrap')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('config', 'config'), ('src/konata_api', 'konata_api')],
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
    name='KonataAPI',
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
    icon=['assets\\icon.ico'],
)
