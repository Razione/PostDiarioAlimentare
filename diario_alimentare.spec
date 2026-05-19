# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None
_is_mac = sys.platform == 'darwin'

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
    hooksconfig={
        "PyQt6": {
            "qt_plugins": [
                "platforms",
                "platforminputcontexts",
                "styles",
                "imageformats",
                "iconengines",
                "permissions",
            ]
        }
    },
    runtime_hooks=['rthook_macos.py'] if _is_mac else [],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
            'CFBundlePackageType': 'APPL',
            'CFBundleExecutable': 'DiarioAlimentare',
            'CFBundleIdentifier': 'it.diarioalimentare.app',
            'CFBundleName': 'Diario Alimentare',
            'CFBundleDisplayName': 'Diario Alimentare',
            'CFBundleShortVersionString': '1.0.0',
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
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
