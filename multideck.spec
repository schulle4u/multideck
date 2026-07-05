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
APP_VERSION = '0.7.4'
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
    'wx.dataview',
    'wx.lib.newevent',
    '_sounddevice_data',
]

# Collect dependency data
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

# Collect PortAudio library for sounddevice
datas += collect_data_files('sounddevice')
datas += collect_data_files('soundfile')
binaries = collect_dynamic_libs('sounddevice')
binaries += collect_dynamic_libs('soundfile')

# Collect Prismatoid's Python modules and native Prism libraries.
# The distribution is named "prismatoid", but the import package is "prism".
prism_datas, prism_binaries, prism_hiddenimports = collect_all('prism')
datas += prism_datas
binaries += prism_binaries
hiddenimports += prism_hiddenimports
hiddenimports += [
    'prism',
    'prism.core',
    'prism.lib',
]

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
        'html',
        'http',
        'xml',
        'pydoc',
        'doctest',
        'difflib',
        'calendar',
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

a_cli = Analysis(
    [os.path.join(PROJECT_ROOT, 'src', 'cli.py')],
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
        'html',
        'http',
        'xml',
        'pydoc',
        'doctest',
        'difflib',
        'calendar',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_cli = PYZ(
    a_cli.pure, 
    a_cli.zipped_data,
    cipher=block_cipher
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name='multideck-cli', # The name of your CLI executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Crucial for CLI visibility
    disable_windowed_traceback=False,
    argv_emulation=IS_MACOS,
    icon=APP_ICON,
)

a_prism_worker = Analysis(
    [os.path.join(PROJECT_ROOT, 'src', 'utils', 'prism_tts_worker.py')],
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
        'html',
        'http',
        'xml',
        'pydoc',
        'doctest',
        'difflib',
        'calendar',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_prism_worker = PYZ(
    a_prism_worker.pure,
    a_prism_worker.zipped_data,
    cipher=block_cipher,
)

exe_prism_worker = EXE(
    pyz_prism_worker,
    a_prism_worker.scripts,
    [],
    exclude_binaries=True,
    name='prism_tts_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    exe_prism_worker,
    a_prism_worker.binaries,
    a_prism_worker.zipfiles,
    a_prism_worker.datas,
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
