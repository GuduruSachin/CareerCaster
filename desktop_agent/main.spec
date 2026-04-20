# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('core/', 'core/'),
        ('../core/', 'core/'), # Include shared core from project root
        ('ui/', 'ui/'),
        ('models/', 'models/'), # Crucial for offline VAD weights
    ],
    hiddenimports=[
        'torch',
        'torchaudio',
        'faster_whisper',
        'pyaudio',
        'numpy',
        'PyQt6',
        'google.genai',
        'google.genai.types',
        'cryptography',
        'pypdf',
        'pandas',
        'streamlit'
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
    console=False, # Set to False for stealth mode GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui/assets/icon.ico' if os.path.exists('ui/assets/icon.ico') else None,
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
