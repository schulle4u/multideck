# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for MultiDeck Audio Player
"""

import os
import sys

block_cipher = None

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))

# Application info
APP_NAME = 'MultiDeck Audio Player'
APP_VERSION = '0.2.3'
APP_ICON = None  # Set to 'assets/icon.ico' if you have an icon

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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
    version='version_info.txt' if os.path.exists(os.path.join(PROJECT_ROOT, 'version_info.txt')) else None,
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
