# -*- mode: python ; coding: utf-8 -*-

import sys


IS_MACOS = sys.platform == "darwin"

# `.icns` is only accepted by PyInstaller on macOS, and `BUNDLE` only
# produces a `.app` there. On Linux the build stops at `dist/English Reader/`.
ICON_FILE = 'assets/EnglishReader.icns'
ICON = [ICON_FILE] if IS_MACOS else None

a = Analysis(
    ['src/english_reader/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='English Reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='English Reader',
)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name='English Reader.app',
        icon=ICON_FILE,
        bundle_identifier=None,
    )
