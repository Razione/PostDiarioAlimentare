# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('database.py', '.'),
    ],
    hiddenimports=[
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.writer.excel',
        'pandas',
        'pandas.io.formats.excel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_is_mac = sys.platform == 'darwin'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DiarioAlimentare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=not _is_mac,        # UPX corrompe i binari macOS
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if _is_mac:
    app = BUNDLE(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='DiarioAlimentare.app',
        bundle_identifier='it.diarioalimentare.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'Diario Alimentare',
        },
    )
else:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='DiarioAlimentare',
    )
