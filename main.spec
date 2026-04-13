# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['desktop_agent/main.py'],
    pathex=[],
    binaries=collect_dynamic_libs('pyaudio'),
    datas=[
        ('assets', 'assets'),
        ('core', 'core'),
    ],
    hiddenimports=[
        'wave',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        'pyaudio',
        'google.genai',
        'numpy',
        'logging.handlers',
        'ctypes.wintypes',
        'multiprocessing',
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CareerCaster',
    debug=True, # Temporarily set to True to catch launch failures
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Set to True to see the console output during debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CareerCaster',
)
