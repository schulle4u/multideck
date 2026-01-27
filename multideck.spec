# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for MultiDeck Audio Player
Cross-platform: Windows, macOS, Linux
"""

import os
import sys
import platform

block_cipher = None

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))

# Detect platform
IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS = platform.system() == 'Darwin'
IS_LINUX = platform.system() == 'Linux'

# Application info
APP_NAME = 'MultiDeck Audio Player'
APP_VERSION = '0.2.3'
APP_BUNDLE_ID = 'com.multideck.audioplayer'

# Platform-specific icon
# Windows: .ico, macOS: .icns, Linux: .png
if IS_WINDOWS:
    APP_ICON = 'assets/icon.ico' if os.path.exists(os.path.join(PROJECT_ROOT, 'assets', 'icon.ico')) else None
elif IS_MACOS:
    APP_ICON = 'assets/icon.icns' if os.path.exists(os.path.join(PROJECT_ROOT, 'assets', 'icon.icns')) else None
else:
    APP_ICON = 'assets/icon.png' if os.path.exists(os.path.join(PROJECT_ROOT, 'assets', 'icon.png')) else None

# Data files to include
datas = []

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'numpy',
    'sounddevice',
    'soundfile',
    'wx',
    'wx.adv',
    'wx.lib.newevent',
    '_sounddevice_data',
]

# Collect sounddevice and soundfile data
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect PortAudio library for sounddevice
datas += collect_data_files('sounddevice')
datas += collect_data_files('soundfile')
binaries = collect_dynamic_libs('sounddevice')
binaries += collect_dynamic_libs('soundfile')

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'src', 'main.py')],
    pathex=[os.path.join(PROJECT_ROOT, 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'html',
        'http',
        'xml',
        'pydoc',
        'doctest',
        'difflib',
        # 'inspect',
        'calendar',
        # 'pickle',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MultiDeck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=IS_MACOS,  # Enable on macOS for drag-and-drop support
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
    # version_info.txt is Windows-specific (PE version info)
    version='version_info.txt' if IS_WINDOWS and os.path.exists(os.path.join(PROJECT_ROOT, 'version_info.txt')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MultiDeck',
)

# macOS: Create .app bundle
if IS_MACOS:
    app = BUNDLE(
        coll,
        name='MultiDeck.app',
        icon=APP_ICON,
        bundle_identifier=APP_BUNDLE_ID,
        info_plist={
            'CFBundleName': APP_NAME,
            'CFBundleDisplayName': APP_NAME,
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleExecutable': 'MultiDeck',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': 'MDAP',
            'LSMinimumSystemVersion': '10.13.0',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription': 'MultiDeck needs microphone access for audio recording.',
            'CFBundleDocumentTypes': [
                {
                    'CFBundleTypeName': 'MultiDeck Project',
                    'CFBundleTypeExtensions': ['mdap'],
                    'CFBundleTypeRole': 'Editor',
                }
            ],
        },
    )
