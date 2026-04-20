# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['desktop_agent/main.py'],
    pathex=[],
    binaries=collect_dynamic_libs('pyaudio'),
    datas=[
        ('desktop_agent/core/', 'core/'),
        ('desktop_agent/ui/', 'ui/'),
        ('desktop_agent/models/', 'models/'), # Crucial for offline VAD weights
        ('assets/', 'assets/'),
    ],
    hiddenimports=[
        'torch',
        'torchaudio',
        'faster_whisper',
        'pyaudio',
        'numpy',
        'PyQt6',
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'google.genai',
        'google.genai.types',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.primitives.hashes',
        'pypdf',
        'pandas',
        'streamlit',
        'wave',
        'logging.handlers',
        'ctypes.wintypes',
        'multiprocessing',
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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, # Set to False for final stealth distribution
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico' if os.path.exists('assets/logo.ico') else None,
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
