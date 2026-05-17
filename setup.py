from setuptools import setup

APP = ['main.py']
OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'PyQt6',
        'pandas',
        'openpyxl',
    ],
    'includes': [
        'database',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.writer.excel',
        'pandas.io.formats.excel',
    ],
    'plist': {
        'CFBundleName': 'Diario Alimentare',
        'CFBundleDisplayName': 'Diario Alimentare',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
    },
}

setup(
    name='DiarioAlimentare',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
