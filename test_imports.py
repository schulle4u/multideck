#!/usr/bin/env python
"""
Test script to verify imports work correctly
"""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

print("Testing imports...")

try:
    from config.defaults import APP_NAME, APP_VERSION
    print(f"[OK] config.defaults imported successfully")
    print(f"  App: {APP_NAME} v{APP_VERSION}")
except ImportError as e:
    print(f"[FAIL] Failed to import config.defaults: {e}")
    sys.exit(1)

try:
    from config.config_manager import ConfigManager
    print(f"[OK] config.config_manager imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import config.config_manager: {e}")
    sys.exit(1)

try:
    from audio.deck import Deck
    print(f"[OK] audio.deck imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import audio.deck: {e}")
    sys.exit(1)

try:
    from utils.i18n import initialize_i18n
    print(f"[OK] utils.i18n imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import utils.i18n: {e}")
    sys.exit(1)

try:
    from utils.helpers import format_time
    print(f"[OK] utils.helpers imported successfully")
except ImportError as e:
    print(f"[FAIL] Failed to import utils.helpers: {e}")
    sys.exit(1)

print("\n[OK] All core module imports successful!")
print("\nNote: GUI and audio modules require wxPython, sounddevice, etc.")
print("Install dependencies with: pip install -r requirements.txt")
